"""Remote M11 acceptance through the production Thread HTTP contract."""
from __future__ import annotations

import time
from collections.abc import Mapping

from capstone_agent.thread_http import HttpThreadSession, ThreadResyncRequired
from capstone_agent.thread_protocol import EventEnvelope, ThreadSnapshot
from capstone_agent.network_diagram import normalize_network_projection

from .m11_session import INSTRUCTIONS, MODELS

READINESS = {"schema": "capstone-m11-readiness/1", "runtime_mode": "m11-provider-free",
             "families": ["pandapower", "pypsa"]}


def preflight(session: HttpThreadSession) -> None:
    if session._request("GET", "/api/v1/validation/m11") != READINESS:
        raise ValueError("validation_mode_mismatch")


def wait_attempt(session: HttpThreadSession, attempt_id: str, context_id: str,
                 selection_revision: str, *, after: int, require_topology: bool,
                 timeout_seconds: float = 180) -> tuple[EventEnvelope, ...]:
    deadline = time.monotonic() + timeout_seconds
    collected: list[EventEnvelope] = []
    types: set[str] = set()
    cursor = after
    while time.monotonic() < deadline:
        try:
            page = session.events(after=cursor)
        except ThreadResyncRequired as error:
            # A truncated receipt cannot establish this Attempt's full evidence.
            raise ValueError("validation_history_resync_required") from error
        for event in page.events:
            if event.event_seq <= cursor:
                raise ValueError("validation_event_cursor_invalid")
            cursor = event.event_seq
            if event.attempt_id != attempt_id:
                continue
            if event.model_context_id != context_id or event.selection_revision != selection_revision:
                raise ValueError("validation_event_identity_mismatch")
            if event.event_type in {"attempt_failed", "attempt_cancelled", "attempt_interrupted"}:
                raise ValueError(event.event_type)
            if event.event_type == "network_layer_unavailable" and require_topology:
                raise ValueError("validation_topology_unavailable")
            if event.event_type in {"attempt_completed", "network_diagram", "network_layer"}:
                collected.append(event)
                types.add(event.event_type)
            if len(collected) > 16:
                raise ValueError("validation_event_capacity")
        if "attempt_completed" in types and (not require_topology or
                {"network_diagram", "network_layer"} <= types):
            return tuple(collected)
        if not page.events:
            time.sleep(1)
    raise TimeoutError("validation_attempt_timeout")


def _check_attempt(snapshot: ThreadSnapshot, events: tuple[EventEnvelope, ...], *,
                   attempt_id: str, family: str) -> dict[str, object]:
    model = snapshot.active_model_context
    completed = next(event for event in events if event.event_type == "attempt_completed")
    result_refs = completed.payload.get("result_refs")
    evidence_refs = completed.payload.get("evidence_refs")
    if not isinstance(result_refs, list) or not result_refs or not isinstance(evidence_refs, list) or not evidence_refs:
        raise ValueError("validation_admitted_references_missing")
    admitted = tuple(result_refs + evidence_refs)
    projections = [item for item in snapshot.result_projections if item.attempt_id == attempt_id]
    if not any(item.status in {"completed", "partial"} for item in projections):
        raise ValueError("validation_result_projection_missing")
    for projection in projections:
        if (projection.model_context_id != model.id or projection.model_revision != model.model_revision
                or projection.model_id != MODELS[family] or projection.result_ref not in result_refs
                or not set(projection.evidence_refs) <= set(evidence_refs)):
            raise ValueError("validation_result_identity_mismatch")
    details: dict[str, object] = {
        "attempt_id": attempt_id, "model_context_id": model.id,
        "model_id": model.model_id, "model_revision": model.model_revision,
        "result_refs": result_refs, "evidence_refs": evidence_refs,
        "result_ids": [item.result_id for item in projections],
    }
    if family == "pypsa":
        diagram_event = next(event for event in events if event.event_type == "network_diagram")
        layer_event = next(event for event in events if event.event_type == "network_layer")
        view = normalize_network_projection({
            "schema": "capstone-network-view/2.0", "ordinal": layer_event.payload["ordinal"],
            "diagram": diagram_event.payload["diagram"], "layer": layer_event.payload["layer"],
        }, admitted_refs=admitted)
        if (view["diagram"]["model"]["id"] != model.model_id
                or view["diagram"]["model"]["revision"] != model.model_revision):
            raise ValueError("validation_diagram_identity_mismatch")
        details.update({"diagram_event_id": diagram_event.event_id,
                        "layer_event_id": layer_event.event_id,
                        "bus_count": len(view["diagram"]["buses"]),
                        "branch_count": len(view["diagram"]["branches"])})
    return details


def run_matrix(session: HttpThreadSession) -> list[dict[str, object]]:
    preflight(session)
    session.create("ieee39")
    models = session.catalog().models
    if not all(any(item.model_id == model and item.available for item in models) for model in MODELS.values()):
        raise ValueError("validation_family_unavailable")
    checks: list[dict[str, object]] = []
    contexts: dict[str, str] = {}

    def command(kind: str, payload: dict[str, object]):
        preflight(session)
        receipt = session.command(kind, payload)
        if receipt.status != "accepted":
            raise ValueError("validation_command_rejected")
        return receipt

    def run(family: str, index: int, *, reopened: bool = False):
        before = session.snapshot()
        receipt = command("send_professional", {"text": INSTRUCTIONS[family][index]})
        if not isinstance(receipt.target, Mapping) or not isinstance(receipt.target.get("attempt_id"), str):
            raise ValueError("validation_attempt_target_missing")
        attempt_id = receipt.target["attempt_id"]
        active = session.snapshot().active_model_context
        if active.model_id != MODELS[family] or active.implementation_family != family:
            raise ValueError("validation_active_model_mismatch")
        events = wait_attempt(session, attempt_id, active.id, active.selection_revision,
                              after=before.last_event_seq, require_topology=family == "pypsa")
        snapshot = session.snapshot()
        if snapshot.active_model_context != active:
            raise ValueError("validation_context_changed_during_attempt")
        details = _check_attempt(snapshot, events, attempt_id=attempt_id, family=family)
        previous = contexts.get(family)
        if previous is not None and ((active.id == previous) == reopened):
            raise ValueError("validation_context_reuse_mismatch")
        contexts[family] = active.id
        checks.append({"id": f"{family}-{'reopened' if reopened else index + 1}",
                       "status": "passed", "details": details})

    run("pandapower", 0)
    run("pandapower", 1)
    command("switch_model", {"model_id": "regional-six-bus"})
    run("pypsa", 0)
    run("pypsa", 1)
    before_reopen = session.snapshot().last_event_seq
    command("reopen_model_context", {"model_id": "regional-six-bus", "reason": "M11 fresh Authority context"})
    run("pypsa", 0, reopened=True)
    reopened = session.events(after=before_reopen)
    if not any(event.event_type == "model_context_reopened" for event in reopened.events):
        raise ValueError("validation_reopen_event_missing")
    return checks
