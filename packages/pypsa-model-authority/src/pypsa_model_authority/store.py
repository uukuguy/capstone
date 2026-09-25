"""Immutable current-run model and result documents."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections.abc import Mapping, Sequence
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
    investment_periods = document.get("investment_periods")
    if investment_periods is None:
        network.set_snapshots(pd.DatetimeIndex(snapshots))
    elif (
        isinstance(investment_periods, list)
        and len(investment_periods) == 2
        and all(isinstance(period, int) and not isinstance(period, bool) for period in investment_periods)
        and investment_periods == sorted(set(investment_periods))
        and len(snapshots) == 2
        and all(isinstance(item, list) and len(item) == 2 for item in snapshots)
        and [item[0] for item in snapshots] == investment_periods
    ):
        network.set_snapshots(pd.MultiIndex.from_tuples(
            [(item[0], pd.Timestamp(item[1])) for item in snapshots],
            names=["period", "timestep"],
        ))
        network.investment_period_weightings.loc[investment_periods, ["objective", "years"]] = 1.0
    else:
        raise ModelStoreError("registered investment periods are invalid")
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
        demand = load["p_set_mw"]
        network.add("Load", load["id"], bus=load["bus"], p_set=0.0 if isinstance(demand, list) else demand)
        if isinstance(demand, list):
            network.loads_t.p_set[load["id"]] = _series_values(demand, len(snapshots))
    for generator in components.get("generators", []):
        network.add(
            "Generator", generator["id"], bus=generator["bus"],
            p_nom=generator["p_nom_mw"], marginal_cost=generator["marginal_cost"],
            committable=generator.get("committable", False),
            start_up_cost=generator.get("start_up_cost", 0.0),
            p_min_pu=generator.get("p_min_pu", 0.0),
            p_nom_extendable=generator.get("p_nom_extendable", False),
            p_nom_max=generator.get("p_nom_max_mw", float("inf")),
            capital_cost=generator.get("capital_cost", 0.0),
            build_year=generator.get("build_year", 0),
            lifetime=generator.get("lifetime", float("inf")),
        )
        limit = generator.get("p_max_pu")
        if isinstance(limit, list):
            network.generators_t.p_max_pu[generator["id"]] = _series_values(limit, len(snapshots))
    for line in components.get("lines", []):
        network.add(
            "Line", line["id"], bus0=line["from_bus"], bus1=line["to_bus"],
            r=line["r_ohm"], x=line["x_ohm"], s_nom=line["s_nom_mva"],
        )
    for link in components.get("links", []):
        if "ambient_temperature_c" in link:
            ambient = _series_values(link["ambient_temperature_c"], len(snapshots))
            baseline, slope = link.get("cop_at_zero_c"), link.get("cop_per_degree_c")
            if (
                link.get("carrier") != "heat-pump" or "efficiency" in link
                or not isinstance(baseline, (int, float)) or isinstance(baseline, bool)
                or not isinstance(slope, (int, float)) or isinstance(slope, bool)
                or not math.isfinite(baseline) or not math.isfinite(slope)
            ):
                raise ModelStoreError("registered heat-pump COP model is invalid")
            efficiency = [float(baseline + slope * temperature) for temperature in ambient]
            if any(not 1.0 <= value <= 10.0 for value in efficiency):
                raise ModelStoreError("registered heat-pump COP is outside its bounds")
        else:
            efficiency = link["efficiency"]
        network.add(
            "Link", link["id"], bus0=link["from_bus"], bus1=link["to_bus"],
            p_nom=link["p_nom_mw"], efficiency=1.0 if isinstance(efficiency, list) else efficiency,
            carrier=link.get("carrier", ""),
            **({"bus2": link["to_bus2"], "efficiency2": link["efficiency2"]} if "to_bus2" in link else {}),
        )
        if isinstance(efficiency, list):
            network.links_t.efficiency[link["id"]] = _series_values(efficiency, len(snapshots))
    for store in components.get("stores", []):
        network.add(
            "Store", store["id"], bus=store["bus"], carrier=store.get("carrier", ""),
            e_nom=store["e_nom_mwh"], e_initial=store.get("e_initial_mwh", 0.0),
            e_cyclic=store.get("e_cyclic", False),
        )
    scenarios = document.get("scenarios")
    if scenarios is not None:
        if (
            not isinstance(scenarios, dict) or len(scenarios) != 2
            or any(not isinstance(name, str) or not name for name in scenarios)
            or any(not isinstance(weight, (int, float)) or isinstance(weight, bool) or weight <= 0 for weight in scenarios.values())
            or abs(sum(scenarios.values()) - 1.0) > 1e-9
        ):
            raise ModelStoreError("registered scenarios are invalid")
        network.set_scenarios(scenarios)
        for load in components.get("loads", []):
            scenario_values = load.get("scenario_p_set_mw")
            if scenario_values is not None:
                if not isinstance(scenario_values, dict) or set(scenario_values) != set(scenarios):
                    raise ModelStoreError("registered scenario demand is invalid")
                for scenario, value in scenario_values.items():
                    network.loads_t.p_set[(scenario, load["id"])] = _series_values([value], len(snapshots))
    return network


def _series_values(values: Sequence[object], count: int) -> list[float]:
    if len(values) != count:
        raise ModelStoreError("registered time series is invalid")
    parsed: list[float] = []
    for value in values:
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ModelStoreError("registered time series is invalid")
        parsed.append(float(value))
    return parsed
