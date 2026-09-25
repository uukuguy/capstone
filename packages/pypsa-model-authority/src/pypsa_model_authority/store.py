"""Immutable current-run model and result documents."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections.abc import Mapping
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import pypsa  # pyright: ignore[reportMissingImports] -- authority venv


Kind = Literal["model", "result", "evidence"]
_DIRECTORY = {"model": "models", "result": "results", "evidence": "evidence"}
_REF = re.compile(r"^pypsa-(model|result|evidence):sha256:([a-f0-9]{64})$")
_RUN_ID = re.compile(r"^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class ModelStoreError(RuntimeError):
    pass


def canonical_bytes(document: Mapping[str, object]) -> bytes:
    return json.dumps(
        dict(document), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def document_ref(kind: Kind, document: Mapping[str, object]) -> str:
    return f"pypsa-{kind}:sha256:{hashlib.sha256(canonical_bytes(document)).hexdigest()}"


class ModelStore:
    def __init__(self, root: Path, *, run_id: str) -> None:
        if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
            raise ModelStoreError("invalid current run identifier")
        self.root = Path(root)
        self.run_id = run_id

    def persist(self, kind: Kind, document: Mapping[str, object]) -> str:
        if document.get("run_id") != self.run_id:
            raise ModelStoreError("document does not belong to current run")
        reference = document_ref(kind, document)
        target = self._path(reference, kind)
        if self.root.is_symlink() or target.parent.is_symlink():
            raise ModelStoreError("authority store path is unsafe")
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = canonical_bytes(document) + b"\n"
        try:
            descriptor = os.open(
                target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
        except FileExistsError:
            if self.load(reference, kind) != dict(document):
                raise ModelStoreError("immutable authority document collision")
            return reference
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise ModelStoreError("authority document write failed") from exc
        return reference

    def load(self, reference: str, kind: Kind) -> dict[str, object]:
        path = self._path(reference, kind)
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                with os.fdopen(descriptor, "rb", closefd=False) as stream:
                    raw = stream.read(1_000_001)
            finally:
                os.close(descriptor)
        except OSError as exc:
            raise ModelStoreError("reference is unavailable in the current run") from exc
        if len(raw) > 1_000_000:
            raise ModelStoreError("authority document exceeds its size limit")
        try:
            document = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ModelStoreError("authority document integrity failed") from exc
        try:
            valid_digest = isinstance(document, dict) and document_ref(kind, document) == reference
        except (TypeError, ValueError):
            valid_digest = False
        if not valid_digest:
            raise ModelStoreError("authority document integrity failed")
        if document.get("run_id") != self.run_id:
            raise ModelStoreError("reference is unavailable in the current run")
        return document

    def model_path(self, reference: str) -> Path:
        return self._path(reference, "model")

    def artifact_path(self, reference: str, kind: Kind) -> Path:
        return self._path(reference, kind)

    def load_model(self, reference: str) -> dict[str, object]:
        document = self.load(reference, "model")
        components = document.get("components")
        if not isinstance(components, dict) or document.get("component_digest") != hashlib.sha256(
            canonical_bytes(components)
        ).hexdigest():
            raise ModelStoreError("model component integrity failed")
        if document.get("schema") != "pypsa-model-revision/1.0":
            raise ModelStoreError("model revision schema is invalid")
        if document.get("pypsa_version") != version("pypsa"):
            raise ModelStoreError("model revision PyPSA version is incompatible")
        return document

    def load_network(self, reference: str) -> pypsa.Network:
        return network_from_revision(self.load_model(reference))

    def _path(self, reference: str, expected_kind: Kind) -> Path:
        matched = _REF.fullmatch(reference) if isinstance(reference, str) else None
        if matched is None or matched.group(1) != expected_kind:
            raise ModelStoreError("invalid authority reference")
        return self.root / _DIRECTORY[expected_kind] / f"{matched.group(2)}.json"


def network_from_revision(document: Mapping[str, object]) -> pypsa.Network:
    import pandas as pd
    import pypsa  # pyright: ignore[reportMissingImports] -- authority venv

    components = document.get("components")
    snapshots = document.get("snapshots")
    weights = document.get("snapshot_weightings")
    if not isinstance(components, dict) or not isinstance(snapshots, list) or not isinstance(weights, list):
        raise ModelStoreError("model revision is incomplete")
    if not snapshots or len(snapshots) != len(weights):
        raise ModelStoreError("model snapshots and weightings differ")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0 for value in weights):
        raise ModelStoreError("model snapshot weightings are invalid")
    network = pypsa.Network()
    network.set_snapshots(pd.DatetimeIndex(snapshots))
    for column in network.snapshot_weightings.columns:
        network.snapshot_weightings[column] = weights
    for carrier in components.get("carriers", []):
        network.add("Carrier", carrier["id"])
    for bus in components.get("buses", []):
        network.add(
            "Bus", bus["id"], v_nom=bus["v_nom_kv"],
            **({"carrier": bus["carrier"]} if "carrier" in bus else {}),
        )
    for load in components.get("loads", []):
        network.add("Load", load["id"], bus=load["bus"], p_set=load["p_set_mw"])
    for generator in components.get("generators", []):
        network.add(
            "Generator", generator["id"], bus=generator["bus"],
            p_nom=generator["p_nom_mw"], marginal_cost=generator["marginal_cost"],
            committable=generator.get("committable", False),
            start_up_cost=generator.get("start_up_cost", 0.0),
            p_nom_extendable=generator.get("p_nom_extendable", False),
            p_nom_max=generator.get("p_nom_max_mw", float("inf")),
            capital_cost=generator.get("capital_cost", 0.0),
        )
    for line in components.get("lines", []):
        network.add(
            "Line", line["id"], bus0=line["from_bus"], bus1=line["to_bus"],
            r=line["r_ohm"], x=line["x_ohm"], s_nom=line["s_nom_mva"],
        )
    for link in components.get("links", []):
        network.add(
            "Link", link["id"], bus0=link["from_bus"], bus1=link["to_bus"],
            p_nom=link["p_nom_mw"], efficiency=link["efficiency"],
            carrier=link.get("carrier", ""),
        )
    return network
