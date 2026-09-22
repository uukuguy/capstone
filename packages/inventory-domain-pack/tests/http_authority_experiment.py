"""Test-only fixed HTTP authority variant for the inventory Domain Pack."""

from __future__ import annotations

import hashlib
import http.client
import json
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from capability_agent._safe_files import ensure_bound_directory
from inventory_domain.authority import InventoryArtifactAuthority, InventoryIntegrityError, VerifiedArtifact
from inventory_reference.artifacts import canonical_json_bytes, load_document, persist_document
from inventory_reference.catalog import load_registered_catalog
from inventory_reference.models import InventoryAsset, InventoryCatalog


_AUTHORITY_ID = "inventory-http-loopback"
_CAPABILITIES = ("catalog.open", "asset.list", "asset.get", "stock.summary")


class HttpInventoryError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class LoopbackInventoryService:
    """Actual loopback HTTP service with fixed, authoritative inventory facts."""

    token = "fixture-inventory-token-only"

    def __init__(self) -> None:
        self.mode = "normal"
        self.requests: list[dict[str, object]] = []
        self.page_requests = 0
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.origin = ""

    def __enter__(self) -> LoopbackInventoryService:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                del format, args

            def do_POST(self) -> None:
                if self.path != "/capability":
                    self.send_error(404)
                    return
                length = int(self.headers.get("content-length", "0"))
                if length <= 0 or length > 64 * 1024:
                    self.send_error(413)
                    return
                try:
                    request = json.loads(self.rfile.read(length))
                except (ValueError, UnicodeDecodeError):
                    self.send_error(400)
                    return
                if not isinstance(request, dict):
                    self.send_error(400)
                    return
                owner.requests.append(request)
                capability = request.get("capability")
                if self.headers.get("authorization") != f"Bearer {owner.token}":
                    self._json(401, {"code": "unauthorized"})
                    return
                if capability != "environment.describe":
                    status = {"unauthorized": 401, "forbidden": 403, "rate_limited": 429}.get(owner.mode)
                    if status is not None:
                        self._json(status, {"code": owner.mode})
                        return
                    if owner.mode == "timeout":
                        time.sleep(0.2)
                arguments = request.get("arguments")
                if not isinstance(capability, str) or not isinstance(arguments, dict):
                    self._json(400, {"code": "invalid_request"})
                    return
                try:
                    data, version = owner._execute(capability, arguments)
                except ValueError:
                    self._json(400, {"code": "invalid_request"})
                    return
                if owner.mode == "schema_drift" and capability != "environment.describe":
                    data = {"unexpected": True}
                if owner.mode == "version_change" and capability == "asset.list" and arguments.get("cursor") == 2:
                    version = "inventory-revision:sha256:" + "0" * 64
                response = {
                    "schema": "inventory-http-response/1.0",
                    "request_id": request.get("request_id"),
                    "authority_id": _AUTHORITY_ID,
                    "catalog_version": version,
                    "data": data,
                }
                if owner.mode == "schema_drift" and capability != "environment.describe":
                    del response["data"]
                self._json(200, response)

            def _json(self, status: int, value: dict[str, object]) -> None:
                body = canonical_json_bytes(value)
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except BrokenPipeError:
                    pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.origin = f"http://127.0.0.1:{self._server.server_port}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        assert self._server is not None and self._thread is not None
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()

    def _execute(self, capability: str, arguments: dict[str, object]) -> tuple[dict[str, object], str]:
        catalog = load_registered_catalog("warehouse-a")
        version = catalog.revision_ref
        if capability == "environment.describe":
            if arguments:
                raise ValueError("unexpected arguments")
            return {
                "protocol": "inventory-capability",
                "protocol_version": "1.0",
                "service": "inventory-http-loopback",
                "service_version": "1.0",
                "executable_capabilities": [{"id": item} for item in _CAPABILITIES],
            }, version
        if capability == "catalog.open":
            if arguments != {"catalog_id": "warehouse-a"}:
                raise ValueError("unknown catalog")
            return {"catalog": catalog.model_dump(mode="json")}, version
        if arguments.get("catalog_id") != "warehouse-a":
            raise ValueError("unknown catalog")
        if capability == "asset.list":
            cursor = arguments.get("cursor", 0)
            limit = arguments.get("limit", 50)
            if type(cursor) is not int or type(limit) is not int or not 0 <= cursor <= 100 or not 1 <= limit <= 100:
                raise ValueError("invalid paging")
            assets = [
                asset for asset in sorted(catalog.assets, key=lambda item: item.asset_id)
                if (arguments.get("category") is None or asset.category == arguments["category"])
                and (arguments.get("location") is None or asset.location == arguments["location"])
            ][:limit]
            selected = assets[cursor:cursor + 2]
            next_cursor = cursor + len(selected) if cursor + len(selected) < len(assets) else None
            self.page_requests += 1
            if self.mode == "partial_page" and cursor == 2:
                raise ValueError("page unavailable")
            return {
                "assets": [asset.model_dump(mode="json") for asset in selected],
                "next_cursor": next_cursor,
                "total_count": len(assets),
            }, version
        if capability == "asset.get":
            asset_id = arguments.get("asset_id")
            asset = next((item for item in catalog.assets if item.asset_id == asset_id), None)
            if asset is None:
                raise ValueError("asset unavailable")
            return {"asset": asset.model_dump(mode="json")}, version
        if capability == "stock.summary":
            return {
                "asset_count": len(catalog.assets),
                "total_quantity_on_hand": sum(asset.quantity_on_hand for asset in catalog.assets),
                "reorder_candidate_count": sum(asset.quantity_on_hand <= asset.reorder_level for asset in catalog.assets),
                "reorder_asset_ids": sorted(
                    asset.asset_id for asset in catalog.assets
                    if asset.quantity_on_hand <= asset.reorder_level
                ),
            }, version
        raise ValueError("capability unavailable")


class HttpInventoryExecutor:
    """Fixed endpoint adapter; domain facts come only from the HTTP response."""

    def __init__(
        self, origin: str, token: str, workspace: Path, *, timeout_seconds: float = 1.0
    ) -> None:
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or parsed.port is None or parsed.path or parsed.query or parsed.fragment
            or parsed.username or parsed.password
        ):
            raise ValueError("HTTP experiment endpoint must be fixed loopback")
        if not token or timeout_seconds <= 0:
            raise ValueError("HTTP experiment credentials or timeout are invalid")
        self._port = parsed.port
        self._token = token
        self.workspace = ensure_bound_directory(workspace)
        self.timeout_seconds = timeout_seconds

    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
        if capability not in (*_CAPABILITIES, "environment.describe"):
            raise HttpInventoryError("capability_not_published")
        if capability == "environment.describe":
            response, _, _ = self._request(capability, arguments)
            environment_data = response.get("data")
            if not isinstance(environment_data, dict):
                raise HttpInventoryError("http_schema_invalid")
            return environment_data
        if capability == "catalog.open":
            response, request_id, observed_at = self._request(capability, arguments)
            data = self._data(response, {"catalog"})
            try:
                catalog = InventoryCatalog.model_validate_json(
                    json.dumps(data["catalog"]), strict=True
                )
            except Exception as exc:
                raise HttpInventoryError("http_schema_invalid") from exc
            revision = catalog.model_dump(mode="json")
            version = self._version(response)
            if version != catalog.revision_ref:
                raise HttpInventoryError("http_version_changed")
            receipt = _receipt(capability, version, [data], [request_id], [observed_at])
            revision_ref, _ = persist_document(self.workspace, "revision", revision)
            context_ref, _ = persist_document(self.workspace, "context", {
                "schema_version": "inventory-context/1.0",
                "catalog_id": catalog.catalog_id,
                "revision_ref": revision_ref,
                "receipt": receipt,
            })
            return {
                "catalog_id": catalog.catalog_id,
                "revision_ref": revision_ref,
                "context_ref": context_ref,
                "asset_count": len(catalog.assets),
            }

        context_ref = arguments.get("context_ref")
        if not isinstance(context_ref, str):
            raise HttpInventoryError("invalid_context_ref")
        try:
            context = load_document(self.workspace, context_ref, "context")
        except (OSError, ValueError) as exc:
            raise HttpInventoryError("invalid_context_ref") from exc
        catalog_id = context.get("catalog_id")
        revision_ref = context.get("revision_ref")
        if not isinstance(catalog_id, str) or not isinstance(revision_ref, str):
            raise HttpInventoryError("invalid_context_ref")
        if capability == "asset.list":
            return self._list_assets(arguments, context_ref, revision_ref, catalog_id)

        selected = {key: value for key, value in arguments.items() if key != "context_ref"}
        selected["catalog_id"] = catalog_id
        response, request_id, observed_at = self._request(capability, selected)
        if self._version(response) != revision_ref:
            raise HttpInventoryError("http_version_changed")
        data: dict[str, object]
        if capability == "asset.get":
            raw = self._data(response, {"asset"})
            try:
                data = {"asset": InventoryAsset.model_validate(raw["asset"], strict=True).model_dump(mode="json")}
            except Exception as exc:
                raise HttpInventoryError("http_schema_invalid") from exc
        else:
            raw = self._data(response, {
                "asset_count", "total_quantity_on_hand", "reorder_candidate_count", "reorder_asset_ids"
            })
            if (
                any(not _nonnegative_int(raw[name]) for name in (
                    "asset_count", "total_quantity_on_hand", "reorder_candidate_count"
                ))
                or not isinstance(raw["reorder_asset_ids"], list)
                or not all(isinstance(item, str) for item in raw["reorder_asset_ids"])
            ):
                raise HttpInventoryError("http_schema_invalid")
            data = raw
        receipt = _receipt(capability, revision_ref, [data], [request_id], [observed_at])
        return self._persist_result(capability, data, receipt, context_ref, revision_ref)
    def _list_assets(
        self, arguments: dict[str, object], context_ref: str,
        revision_ref: str, catalog_id: str,
    ) -> dict[str, object]:
        limit = arguments.get("limit", 50)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise HttpInventoryError("invalid_arguments")
        requested = {key: value for key, value in arguments.items() if key != "context_ref"}
        requested.update({"catalog_id": catalog_id, "limit": limit})
        pages: list[dict[str, object]] = []
        request_ids: list[str] = []
        observed: list[str] = []
        assets: list[dict[str, object]] = []
        cursor: int | None = 0
        total_count: int | None = None
        seen: set[int] = set()
        while cursor is not None:
            if cursor in seen or len(pages) >= 100:
                raise HttpInventoryError("http_pagination_incomplete")
            seen.add(cursor)
            try:
                response, request_id, observed_at = self._request(
                    "asset.list", {**requested, "cursor": cursor}
                )
            except HttpInventoryError as exc:
                if pages:
                    raise HttpInventoryError("http_pagination_incomplete") from exc
                raise
            if self._version(response) != revision_ref:
                raise HttpInventoryError("http_version_changed")
            raw = self._data(response, {"assets", "next_cursor", "total_count"})
            next_cursor = raw["next_cursor"]
            count = raw["total_count"]
            if (
                not isinstance(raw["assets"], list)
                or type(count) is not int or count < 0 or count > limit
                or (next_cursor is not None and (type(next_cursor) is not int or next_cursor <= cursor))
                or (total_count is not None and count != total_count)
            ):
                raise HttpInventoryError("http_schema_invalid")
            try:
                validated = [
                    InventoryAsset.model_validate(item, strict=True).model_dump(mode="json")
                    for item in raw["assets"]
                ]
            except Exception as exc:
                raise HttpInventoryError("http_schema_invalid") from exc
            assets.extend(validated)
            if len(assets) > count:
                raise HttpInventoryError("http_schema_invalid")
            pages.append({"assets": validated, "next_cursor": next_cursor, "total_count": count})
            request_ids.append(request_id)
            observed.append(observed_at)
            total_count = count
            cursor = next_cursor
        if total_count is None or len(assets) != total_count:
            raise HttpInventoryError("http_pagination_incomplete")
        data = {
            "assets": assets,
            "count": len(assets),
            "filters": {key: arguments[key] for key in ("category", "location") if arguments.get(key) is not None},
        }
        receipt = _receipt("asset.list", revision_ref, pages, request_ids, observed)
        return self._persist_result("asset.list", data, receipt, context_ref, revision_ref)

    def _persist_result(
        self, capability: str, data: dict[str, object], receipt: dict[str, object],
        context_ref: str, revision_ref: str,
    ) -> dict[str, object]:
        result_ref, _ = persist_document(self.workspace, "result", {
            "schema_version": "inventory-result/1.0",
            "capability": capability,
            "context_ref": context_ref,
            "revision_ref": revision_ref,
            "data": data,
            "receipt": receipt,
        })
        evidence_ref, _ = persist_document(self.workspace, "evidence", {
            "schema_version": "inventory-evidence/1.0",
            "capability": capability,
            "context_ref": context_ref,
            "revision_ref": revision_ref,
            "result_ref": result_ref,
            "facts": data,
        })
        return {
            **data,
            "capability": capability,
            "context_ref": context_ref,
            "revision_ref": revision_ref,
            "result_ref": result_ref,
            "evidence_refs": [evidence_ref],
        }

    def _request(
        self, capability: str, arguments: dict[str, object]
    ) -> tuple[dict[str, object], str, str]:
        request_id = f"http-{uuid4().hex}"
        payload = canonical_json_bytes({
            "request_id": request_id,
            "capability": capability,
            "arguments": arguments,
        })
        connection = http.client.HTTPConnection("127.0.0.1", self._port, timeout=self.timeout_seconds)
        try:
            connection.request("POST", "/capability", body=payload, headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            })
            response = connection.getresponse()
            raw = response.read(1024 * 1024 + 1)
            observed_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        except (TimeoutError, socket.timeout) as exc:
            raise HttpInventoryError("http_timeout") from exc
        except (OSError, http.client.HTTPException) as exc:
            raise HttpInventoryError("http_transport_failed") from exc
        finally:
            connection.close()
        if len(raw) > 1024 * 1024:
            raise HttpInventoryError("http_response_too_large")
        if response.status != 200:
            code = {401: "http_unauthorized", 403: "http_forbidden", 429: "http_rate_limited"}.get(
                response.status, "http_remote_failure"
            )
            raise HttpInventoryError(code)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HttpInventoryError("http_schema_invalid") from exc
        if (
            not isinstance(value, dict)
            or set(value) != {"schema", "request_id", "authority_id", "catalog_version", "data"}
            or value["schema"] != "inventory-http-response/1.0"
            or value["request_id"] != request_id
            or value["authority_id"] != _AUTHORITY_ID
            or not isinstance(value["catalog_version"], str)
        ):
            raise HttpInventoryError("http_schema_invalid")
        return value, request_id, observed_at

    @staticmethod
    def _data(response: dict[str, object], keys: set[str]) -> dict[str, object]:
        data = response["data"]
        if not isinstance(data, dict) or set(data) != keys:
            raise HttpInventoryError("http_schema_invalid")
        return data

    @staticmethod
    def _version(response: dict[str, object]) -> str:
        version = response["catalog_version"]
        if not isinstance(version, str) or not version.startswith("inventory-revision:sha256:"):
            raise HttpInventoryError("http_schema_invalid")
        return version


def _nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _receipt(
    operation: str, version: str, pages: list[dict[str, object]],
    request_ids: list[str], observed_at: list[str],
) -> dict[str, object]:
    return {
        "schema_version": "inventory-http-receipt/1.0",
        "authority_id": _AUTHORITY_ID,
        "operation": operation,
        "catalog_version": version,
        "request_ids": request_ids,
        "observed_at": observed_at,
        "page_count": len(pages),
        "complete": True,
        "response_sha256": hashlib.sha256(canonical_json_bytes({"pages": pages})).hexdigest(),
        "pages": pages,
    }


class HttpInventoryArtifactAuthority(InventoryArtifactAuthority):
    """Verify local receipts and domain artifact lineage on offline replay."""

    def _verify_context(self, reference: str) -> VerifiedArtifact:
        artifact = super()._verify_context(reference)
        version = artifact.document.get("revision_ref")
        receipt = _verified_receipt(artifact.document.get("receipt"), "catalog.open", version)
        revision = load_document(self.workspace_root, str(version), "revision")
        pages = receipt["pages"]
        if pages != [{"catalog": revision}]:
            raise InventoryIntegrityError("HTTP catalog receipt does not match revision")
        return artifact

    def verify_result(self, reference: str) -> VerifiedArtifact:
        artifact = super().verify_result(reference)
        capability = artifact.document.get("capability")
        version = artifact.document.get("revision_ref")
        receipt = _verified_receipt(artifact.document.get("receipt"), capability, version)
        data = artifact.document.get("data")
        pages = receipt["pages"]
        if capability == "asset.list":
            assets = [item for page in pages for item in page.get("assets", [])]
            if not isinstance(data, dict) or data.get("assets") != assets or data.get("count") != len(assets):
                raise InventoryIntegrityError("HTTP asset receipt does not match result")
            if pages[-1].get("next_cursor") is not None or pages[-1].get("total_count") != len(assets):
                raise InventoryIntegrityError("HTTP asset receipt is incomplete")
        elif pages != [data]:
            raise InventoryIntegrityError("HTTP receipt does not match result")
        return artifact


def _verified_receipt(value: object, operation: object, version: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "authority_id", "operation", "catalog_version",
        "request_ids", "observed_at", "page_count", "complete",
        "response_sha256", "pages",
    }:
        raise InventoryIntegrityError("HTTP receipt is missing or malformed")
    pages = value["pages"]
    request_ids = value["request_ids"]
    observed_at = value["observed_at"]
    if (
        value["schema_version"] != "inventory-http-receipt/1.0"
        or value["authority_id"] != _AUTHORITY_ID
        or value["operation"] != operation
        or value["catalog_version"] != version
        or value["complete"] is not True
        or not isinstance(pages, list) or not pages
        or not all(isinstance(page, dict) for page in pages)
        or value["page_count"] != len(pages)
        or not isinstance(request_ids, list) or len(request_ids) != len(pages)
        or not all(isinstance(item, str) and item.startswith("http-") for item in request_ids)
        or not isinstance(observed_at, list) or len(observed_at) != len(pages)
        or not all(isinstance(item, str) and item for item in observed_at)
        or value["response_sha256"] != hashlib.sha256(canonical_json_bytes({"pages": pages})).hexdigest()
    ):
        raise InventoryIntegrityError("HTTP receipt failed offline verification")
    return value


@dataclass(slots=True)
class PreparedHttpInventoryEndpoint:
    executor: HttpInventoryExecutor
    metadata: dict[str, object]
    closed: bool = False

    def close(self) -> None:
        self.closed = True


class HttpInventoryProvisioner:
    def __init__(self, origin: str, *, timeout_seconds: float = 1.0) -> None:
        self._origin = origin
        self._timeout_seconds = timeout_seconds

    def prepare(self, *, binding: object, workspace: Path, credentials: object) -> PreparedHttpInventoryEndpoint:
        scope = getattr(binding, "credential_scope")
        if (
            scope.credential_names != ("INVENTORY_API_TOKEN",)
            or getattr(credentials, "scope_id") != scope.scope_id
        ):
            raise ValueError("HTTP inventory credential scope is invalid")
        values = dict(getattr(credentials, "credentials"))
        if set(values) != {"INVENTORY_API_TOKEN"} or not values["INVENTORY_API_TOKEN"]:
            raise ValueError("HTTP inventory credentials are invalid")
        executor = HttpInventoryExecutor(
            self._origin, values["INVENTORY_API_TOKEN"], workspace,
            timeout_seconds=self._timeout_seconds,
        )
        return PreparedHttpInventoryEndpoint(
            executor=executor,
            metadata={
                "binding_id": getattr(binding, "binding_id"),
                "authority_id": _AUTHORITY_ID,
                "transport": "fixed-http-loopback",
                "timeout_seconds": self._timeout_seconds,
            },
        )
