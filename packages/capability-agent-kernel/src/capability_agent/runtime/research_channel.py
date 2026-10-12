"""Private host-owned research requests; no model-selected filesystem paths."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path

from pydantic import ValidationError

from capability_agent._safe_files import ensure_bound_directory, read_bound_regular_path, write_bound_text
from capability_agent.application import ContextStoreError, ResearchController, ResearchUpdate
from capability_agent.application.research_models import research_depth_tool_schema, research_tool_schemas

_IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_MAX_REQUEST_BYTES = 1_048_576


class ResearchRequestChannel:
    """Serve a bounded batch during RPC waits and publish views before receipts."""

    def __init__(self, controller: ResearchController, *, attempt_id: str,
                 is_active: Callable[[], bool], channel_root: Path | None = None) -> None:
        if not _IDENTITY.fullmatch(attempt_id):
            raise ValueError("invalid research attempt identity")
        self.controller = controller
        self.attempt_id = attempt_id
        self.is_active = is_active
        self.root = ensure_bound_directory(channel_root if channel_root is not None
            else controller.store.workspace.core_path / "research" / attempt_id)
        self.requests_path = ensure_bound_directory(self.root / "requests")
        self.receipts_path = ensure_bound_directory(self.root / "receipts")
        self.view_path = self.root / "view.json"
        read_schema, update_schema = research_tool_schemas()
        self._write(self.root / "binding.json", {
            "schema_version": "capability-research-channel/1.0",
            "run_id": controller.store.snapshot.run_id,
            "turn_id": controller.turn_id,
            "attempt_id": attempt_id,
            "research_id": controller.research_id,
            "read_tool_schema": read_schema,
            "update_tool_schema": update_schema,
            "depth_tool_schema": research_depth_tool_schema(),
        })
        self.publish_view()

    def publish_view(self) -> None:
        state = self.controller.read()
        self._write(self.view_path, {
            "schema_version": "capability-research-view/1.0",
            "run_id": self.controller.store.snapshot.run_id,
            "turn_id": self.controller.turn_id,
            "attempt_id": self.attempt_id,
            "research_id": self.controller.research_id,
            "research_revision": state.revision if state else 0,
            "state": state.model_dump(mode="json") if state else None,
        })

    def drain(self, *, max_requests: int = 16) -> int:
        if type(max_requests) is not int or not 1 <= max_requests <= 16:
            raise ValueError("research batch must contain one to sixteen requests")
        handled = 0
        for path in sorted(self.requests_path.glob("*.json")):
            request_id = path.stem
            if not _IDENTITY.fullmatch(request_id):
                raise RuntimeError("invalid research request filename")
            raw = read_bound_regular_path(path)
            if len(raw) > _MAX_REQUEST_BYTES:
                raise RuntimeError("research request exceeds byte limit")
            digest = sha256(raw).hexdigest()
            ack_path = self.receipts_path / path.name
            if ack_path.exists() or ack_path.is_symlink():
                ack = json.loads(read_bound_regular_path(ack_path))
                if ack.get("request_sha256") != digest:
                    raise RuntimeError("research request changed after receipt")
                if ack.get("status") != "not_confirmed":
                    continue
            ack = self._process(raw, request_id)
            ack["schema_version"] = "capability-research-receipt/1.0"
            ack["run_id"] = self.controller.store.snapshot.run_id
            ack["turn_id"] = self.controller.turn_id
            ack["attempt_id"] = self.attempt_id
            ack["request_id"] = request_id
            ack["request_sha256"] = digest
            self._write(ack_path, ack)
            handled += 1
            if handled == max_requests:
                break
        return handled

    def _process(self, raw: bytes, request_id: str) -> dict[str, object]:
        try:
            request = ResearchUpdate.model_validate_json(raw)
            if request.request_id != request_id:
                return {"status": "rejected", "code": "request_identity_mismatch"}
        except ValidationError as exc:
            errors = exc.errors(include_input=False, include_context=False, include_url=False)
            return {"status": "rejected", "code": "invalid_research_update",
                    "validation_errors": [{"path": [part[:128] if isinstance(part, str) else part
                        for part in error["loc"][:12]], "code": error["type"],
                        "message": str(error["msg"])[:256] if error["type"] != "json_invalid"
                        else "Request must be a valid JSON object"} for error in errors[:8]],
                    "validation_errors_truncated": len(errors) > 8}
        except ValueError:
            return {"status": "rejected", "code": "invalid_research_update"}
        try:
            document = request.model_dump(mode="json", exclude_unset=True)
            committed = self.controller.lookup_receipt(document)
            if committed is None:
                if not self.is_active():
                    return {"status": "rejected", "code": "attempt_closed"}
                state = self.controller.read()
                revision = state.revision if state else 0
                if revision != request.expected_revision:
                    return {"status": "rejected", "code": "research_revision_conflict",
                            "research_revision": revision}
                if state is None and request.changes.goal is None:
                    return {"status": "rejected", "code": "research_goal_required",
                            "message": "The first research update requires changes.goal; no update was committed."}
                if any(not self.controller.admit_reference(ref) for ref in request.changes.references()):
                    return {"status": "rejected", "code": "research_reference_not_admitted"}
                committed = self.controller.update(document)
        except ContextStoreError:
            # A storage failure can have an uncertain outcome. Never label it a rollback.
            return {"status": "not_confirmed", "code": "research_update_not_confirmed"}
        self.publish_view()
        return {"status": "committed", "receipt": committed.model_dump(mode="json")}

    @staticmethod
    def _write(path: Path, document: dict[str, object]) -> None:
        write_bound_text(path, json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n")
