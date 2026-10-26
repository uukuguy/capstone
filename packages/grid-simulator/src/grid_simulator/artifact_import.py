"""Bounded, data-only admission of host-granted pandapower artifacts."""

from __future__ import annotations

import json
import math
import re
import stat
import zipfile
from datetime import datetime, timezone

from grid_simulator.evidence import (
    canonical_json,
    fingerprint,
    write_json,
    write_network,
)

import pandas as pd
import pandapower as pp


class ModelImportError(ValueError):
    pass


def grant_fingerprint(document):
    return fingerprint(
        json.dumps(
            {k: v for k, v in document.items() if k != "input_ref"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )


def _read_private(root, path, limit):
    # All paths are fixed by the Authority. Reject symlinks in every component.
    relative = path.relative_to(root)
    current = root
    if root.is_symlink():
        raise ModelImportError("Input workspace must not be a symbolic link")
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ModelImportError("Input storage must not use symbolic links")
    if not path.is_file() or path.stat().st_size > limit:
        raise ModelImportError(
            "Input object is missing or exceeds the processing budget"
        )
    with path.open("rb") as handle:
        payload = handle.read(limit + 1)
    if len(payload) > limit:
        raise ModelImportError("Input object exceeds the processing budget")
    return payload


def _resolve_grant(workspace, input_ref):
    if not isinstance(input_ref, str) or not re.fullmatch(
        r"input:sha256:[0-9a-f]{64}", input_ref
    ):
        raise ModelImportError("Invalid input reference")
    root = workspace.root
    binding = _json(
        _read_private(root, root / "application-model-input-binding.json", 16384)
    )
    grant = _json(
        _read_private(
            root, root / "inputs" / "grants" / f"{input_ref.split(':')[-1]}.json", 32768
        )
    )
    if (
        not isinstance(binding, dict)
        or set(binding) != {"schema", "task_id", "attempt_id", "authority"}
        or binding["schema"] != "grid-model-input-binding/1"
    ):
        raise ModelImportError("Missing host execution binding")
    required = {
        "schema",
        "input_ref",
        "task_id",
        "attempt_id",
        "authority",
        "artifact_ref",
        "bundle_sha256",
        "bundle_bytes",
        "engine",
        "engine_version",
        "model_id",
        "model_revision",
        "scenario_revision",
        "map_sha256",
        "allow_demo",
        "expires_at",
        "revoked",
    }
    if (
        not isinstance(grant, dict)
        or set(grant) != required
        or grant["schema"] != "grid-model-input-grant/1"
        or grant["input_ref"] != input_ref
        or grant_fingerprint(grant) != input_ref.split(":")[-1]
    ):
        raise ModelImportError("Invalid input grant")
    if (
        any(grant[k] != binding[k] for k in ("task_id", "attempt_id", "authority"))
        or grant["authority"] != "grid-simulator"
        or grant["revoked"] is not False
    ):
        raise ModelImportError("Input grant is outside this execution binding")
    try:
        expires = datetime.fromisoformat(grant["expires_at"].replace("Z", "+00:00"))
        if expires.tzinfo is None or expires <= datetime.now(timezone.utc):
            raise ValueError("expired")
    except (ValueError, TypeError, AttributeError) as exc:
        raise ModelImportError("Input grant is expired or invalid") from exc
    if (
        grant["engine"] != "pandapower"
        or grant["engine_version"] != "3.4.0"
        or type(grant["allow_demo"]) is not bool
        or type(grant["bundle_bytes"]) is not int
        or grant["bundle_bytes"] <= 0
    ):
        raise ModelImportError("Unsupported input engine or grant metadata")
    for key in ("bundle_sha256", "map_sha256", "artifact_ref"):
        if not isinstance(grant[key], str) or not re.fullmatch(
            "[0-9a-f]{64}", grant[key]
        ):
            raise ModelImportError("Invalid input content identity")
    return grant


def _validate_mapping(mapping, net, grant):
    identities = {
        "schema": "gateway-element-map/1",
        "engine": grant["engine"],
        "engine_version": grant["engine_version"],
        "artifact_ref": grant["artifact_ref"],
        "model_ref": grant["model_id"],
        "model_revision": grant["model_revision"],
        "scenario_revision": grant["scenario_revision"],
    }
    if not isinstance(mapping, dict) or any(
        mapping.get(k) != v for k, v in identities.items()
    ):
        raise ModelImportError("Mapping identity does not match input grant")
    supported = {
        "bus",
        "line",
        "trafo",
        "trafo3w",
        "load",
        "sgen",
        "gen",
        "ext_grid",
        "switch",
    }
    covered = mapping.get("covered_element_tables")
    if (
        not isinstance(covered, list)
        or any(t not in supported for t in covered)
        or len(set(covered)) != len(covered)
    ):
        raise ModelImportError("Unsupported mapping coverage")
    if any(len(net[t]) for t in supported - set(covered)):
        raise ModelImportError("Mapping omits native tables")
    # The first import profile deliberately excludes other populated input tables.
    for table, value in net.items():
        if (
            isinstance(value, pd.DataFrame)
            and not table.startswith("res_")
            and table not in supported | {"poly_cost"}
            and len(value)
        ):
            raise ModelImportError("Unsupported populated native table")
    elements = mapping.get("elements")
    if not isinstance(elements, list) or len(elements) > 200000:
        raise ModelImportError("Invalid mapping elements")
    indexed = {}
    refs = set()
    for row in elements:
        if (
            not isinstance(row, dict)
            or row.get("element_table") not in covered
            or type(row.get("element_key")) is not int
            or not isinstance(row.get("element_ref"), str)
        ):
            raise ModelImportError("Mapping keys must use exact native integer types")
        key = (row["element_table"], row["element_key"])
        if (
            key in indexed
            or row["element_ref"] in refs
            or key[1] not in net[key[0]].index
        ):
            raise ModelImportError("Mapping contains duplicate or unknown native keys")
        indexed[key] = row
        refs.add(row["element_ref"])
    expected = {(table, int(key)) for table in covered for key in net[table].index}
    if set(indexed) != expected:
        raise ModelImportError("Mapping native coverage is incomplete")
    roles = {
        "line": {"from": "from_bus", "to": "to_bus"},
        "trafo": {"hv": "hv_bus", "lv": "lv_bus"},
        "trafo3w": {"hv": "hv_bus", "mv": "mv_bus", "lv": "lv_bus"},
        "load": {"bus": "bus"},
        "gen": {"bus": "bus"},
        "sgen": {"bus": "bus"},
        "ext_grid": {"bus": "bus"},
    }
    for (table, index), row in indexed.items():
        for endpoint in row.get("endpoints", []):
            if (
                not isinstance(endpoint, dict)
                or endpoint.get("element_table") != "bus"
                or type(endpoint.get("element_key")) is not int
            ):
                raise ModelImportError("Invalid mapped endpoint")
            bus = indexed.get(("bus", endpoint["element_key"]))
            field = roles.get(table, {}).get(endpoint.get("role"))
            if (
                bus is None
                or bus["element_ref"] != endpoint.get("element_ref")
                or field is None
                or net[table].at[index, field] != endpoint["element_key"]
            ):
                raise ModelImportError("Mapped endpoint does not match native topology")
    for table in supported:
        for field in net[table].columns:
            if field == "bus" or field.endswith("_bus"):
                for key in net[table][field]:
                    if (
                        type(key) is bool
                        or pd.isna(key)
                        or int(key) != key
                        or int(key) not in net.bus.index
                    ):
                        raise ModelImportError(
                            "Native endpoint references an unknown bus"
                        )


def import_artifact(workspace, engine, input_ref):
    grant = _resolve_grant(workspace, input_ref)
    archive_path = (
        workspace.root / "inputs" / "objects" / f"{grant['bundle_sha256']}.zip"
    )
    archive_bytes = _read_private(workspace.root, archive_path, 64 * 1024 * 1024)
    if (
        len(archive_bytes) != grant["bundle_bytes"]
        or fingerprint(archive_bytes) != grant["bundle_sha256"]
    ):
        raise ModelImportError("Archive identity does not match input grant")
    import io

    required = {
        "model.pandapower.json",
        "element-map.json",
        "quality.json",
        "demo-assumptions.json",
        "calculation-structure.json",
        "source-model.json",
    }
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            members = archive.infolist()
            if (
                len(members) != len(required)
                or {m.filename for m in members} != required
                or sum(m.file_size for m in members) > 256 * 1024 * 1024
                or any(
                    m.file_size
                    > (160 if m.filename == "source-model.json" else 64) * 1024 * 1024
                    or m.flag_bits & 1
                    or stat.S_ISLNK(m.external_attr >> 16)
                    or m.is_dir()
                    for m in members
                )
            ):
                raise ModelImportError("Unsafe or unsupported archive members")
            contents = {}
            for member in members:
                if member.filename in {
                    "model.pandapower.json",
                    "element-map.json",
                    "quality.json",
                    "demo-assumptions.json",
                }:
                    contents[member.filename] = archive.read(member)
                else:
                    # Check archive integrity without retaining unused source records.
                    with archive.open(member) as stream:
                        while stream.read(1024 * 1024):
                            pass
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise ModelImportError("Invalid archive") from exc
    if fingerprint(contents["element-map.json"]) != grant["map_sha256"]:
        raise ModelImportError("Mapping digest does not match grant")
    net = decode_network(contents["model.pandapower.json"].decode("utf-8"))
    mapping = _json(contents["element-map.json"])
    _validate_mapping(mapping, net, grant)
    quality = _json(contents["quality.json"]).get("quality", {})
    flags = {
        k: quality.get(k)
        for k in ("demo_only", "power_flow_ready", "real_power_flow_ready")
    }
    if (
        any(type(v) is not bool for v in flags.values())
        or flags["demo_only"]
        and not grant["allow_demo"]
    ):
        raise ModelImportError("Input demo permission or readiness flags are invalid")
    serialized = engine.serialize(net)
    # Verify that the persisted representation remains inside the data-only profile.
    decode_network(serialized)
    revision_ref = "revision:sha256:" + fingerprint(serialized)
    mapping_ref = "mapping:sha256:" + fingerprint(contents["element-map.json"])
    lineage = {
        "origin": "imported",
        "model_id": grant["model_id"],
        "revision_ref": revision_ref,
        "engine": engine.name,
        "engine_version": engine.version,
        "parent_context_ref": None,
        "artifact_ref": grant["artifact_ref"],
        "bundle_sha256": grant["bundle_sha256"],
        "model_revision": grant["model_revision"],
        "scenario_revision": grant["scenario_revision"],
        "map_sha256": grant["map_sha256"],
        "mapping_ref": mapping_ref,
        "quality": quality,
        "assumptions": _json(contents["demo-assumptions.json"]),
        "source_snapshot": mapping.get("source_snapshot"),
        "capture": mapping.get("capture"),
        **flags,
    }
    receipt_ref = "import-receipt:sha256:" + fingerprint(canonical_json(lineage))
    lineage["import_receipt_ref"] = receipt_ref
    lineage_ref = "lineage:sha256:" + fingerprint(canonical_json(lineage))
    document = {
        "model_id": grant["model_id"],
        "revision_ref": revision_ref,
        "engine": engine.name,
        "engine_version": engine.version,
        "origin": "imported",
        "parent_context_ref": None,
        "lineage_ref": lineage_ref,
    }
    context_ref = "context:sha256:" + fingerprint(canonical_json(document))
    write_network(workspace.model_artifact(revision_ref), serialized)
    from grid_simulator.evidence import write_bytes_atomic

    write_bytes_atomic(
        workspace.root / "evidence" / "mappings" / f"{grant['map_sha256']}.json",
        contents["element-map.json"],
    )
    receipt = {k: v for k, v in lineage.items() if k != "import_receipt_ref"}
    write_json(
        workspace.root / "evidence" / "imports" / f"{receipt_ref.split(':')[-1]}.json",
        receipt,
    )
    write_json(workspace.lineage_document(lineage_ref), lineage)
    write_json(workspace.context_document(context_ref), document)
    return {
        "context_ref": context_ref,
        "revision_ref": revision_ref,
        "model_id": grant["model_id"],
        "model": grant["model_id"],
        "engine": engine.name,
        "engine_version": engine.version,
        "pandapower_version": engine.version,
        "import_receipt_ref": receipt_ref,
        "mapping_ref": mapping_ref,
        **{
            k: grant[k]
            for k in (
                "artifact_ref",
                "model_revision",
                "scenario_revision",
                "map_sha256",
            )
        },
        **flags,
    }


def _plain(value, depth=0):
    if depth > 40:
        raise ModelImportError("Data nesting exceeds the import budget")
    if isinstance(value, dict):
        if any(not isinstance(k, str) or k.startswith("_") for k in value):
            raise ModelImportError("Serialized objects are not allowed")
        for item in value.values():
            _plain(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _plain(item, depth + 1)
    elif value is not None and type(value) not in (str, bool, int, float):
        raise ModelImportError("Only JSON data is allowed")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ModelImportError("Nonfinite JSON values are not allowed")


def _json(payload):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ModelImportError("Duplicate JSON keys are not allowed")
            result[key] = value
        return result

    try:
        return json.loads(payload, object_pairs_hook=unique)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ModelImportError("Invalid JSON data") from exc


def decode_network(payload: str):
    if len(payload.encode("utf-8")) > 64 * 1024 * 1024:
        raise ModelImportError("Model exceeds the processing budget")
    document = _json(payload)
    if (
        not isinstance(document, dict)
        or set(document) != {"_module", "_class", "_object"}
        or document["_module"] != "pandapower.auxiliary"
        or document["_class"] != "pandapowerNet"
    ):
        raise ModelImportError("Unsupported native network envelope")
    body = document["_object"]
    if not isinstance(body, dict) or body.get("version") != "3.4.0":
        raise ModelImportError("Unsupported engine version")
    net = pp.create_empty_network()
    metadata = {
        "version",
        "format_version",
        "converged",
        "OPF_converged",
        "name",
        "f_hz",
        "sn_mva",
        "std_types",
        "user_pf_options",
        "gateway_quality",
        "gateway_demo_profile",
    }
    for name, value in body.items():
        if name in net and isinstance(net[name], pd.DataFrame):
            if (
                not isinstance(value, dict)
                or value.get("_module") != "pandas.core.frame"
                or value.get("_class") != "DataFrame"
                or value.get("orient") != "split"
                or value.get("is_multiindex") is not False
                or value.get("is_multicolumn") is not False
                or set(value) - {"dtype"}
                != {
                    "_module",
                    "_class",
                    "_object",
                    "orient",
                    "is_multiindex",
                    "is_multicolumn",
                }
            ):
                raise ModelImportError("Unsupported table envelope")
            table = _json(value["_object"])
            if not isinstance(table, dict) or set(table) != {
                "columns",
                "index",
                "data",
            }:
                raise ModelImportError("Only split table data is supported")
            columns, indices, rows = table["columns"], table["index"], table["data"]
            if (
                not all(isinstance(item, list) for item in (columns, indices, rows))
                or len(indices) != len(rows)
                or len(rows) > 200000
                or len(columns) > 100
            ):
                raise ModelImportError("Invalid table dimensions")
            if any(type(i) is not int or i < 0 or i > 2**53 for i in indices) or len(
                set(indices)
            ) != len(indices):
                raise ModelImportError("Table keys must be unique nonnegative integers")
            allowed = set(net[name].columns) | {
                "min_vm_pu",
                "max_vm_pu",
                "max_loading_percent",
                "min_p_mw",
                "max_p_mw",
                "min_q_mvar",
                "max_q_mvar",
                "controllable",
                "oltc",
            }
            if any(not isinstance(c, str) or c not in allowed for c in columns) or len(
                set(columns)
            ) != len(columns):
                raise ModelImportError("Unsupported table columns")
            if any(
                not isinstance(r, list)
                or len(r) != len(columns)
                or any(isinstance(v, (list, dict)) for v in r)
                for r in rows
            ):
                raise ModelImportError("Table cells must be scalar data")
            _plain(rows)
            dtype = value.get("dtype", {})
            if (
                not isinstance(dtype, dict)
                or set(dtype) != set(columns)
                or any(
                    d
                    not in {
                        "object",
                        "bool",
                        "float64",
                        "int64",
                        "Int64",
                        "uint32",
                        "uint64",
                        "int32",
                    }
                    for d in dtype.values()
                )
            ):
                raise ModelImportError("Unsupported table dtype")
            if name in {"controller", "group"} and rows:
                raise ModelImportError("Controllers and groups are not supported")
            if rows and name.startswith("res_"):
                raise ModelImportError(
                    "External result tables are not Authority evidence"
                )
            for position, column in enumerate(columns):
                for row in rows:
                    item = row[position]
                    kind = dtype[column]
                    if kind == "bool" and type(item) is not bool:
                        raise ModelImportError(
                            "Boolean columns require JSON boolean values"
                        )
                    if (
                        kind in {"int64", "Int64", "int32", "uint32", "uint64"}
                        and item is not None
                        and (type(item) not in {int, float} or int(item) != item)
                    ):
                        raise ModelImportError(
                            "Integer columns require integral numeric values"
                        )
                    if (
                        kind == "float64"
                        and item is not None
                        and type(item) not in {int, float}
                    ):
                        raise ModelImportError("Numeric columns require numeric values")
            try:
                net[name] = pd.DataFrame(
                    rows, columns=columns, index=pd.Index(indices, dtype="int64")
                ).astype(dtype)
            except (ValueError, TypeError, OverflowError) as exc:
                raise ModelImportError("Invalid table scalar type") from exc
        elif name in metadata:
            _plain(value)
            if name == "user_pf_options" and value:
                raise ModelImportError("External solver options are not supported")
            net[name] = value
        else:
            raise ModelImportError("Unsupported native network field")
    net.converged = False
    net.OPF_converged = False
    return net
