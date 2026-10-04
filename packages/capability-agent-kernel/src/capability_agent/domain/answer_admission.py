"""Domain-owned admission of a reader answer before its durable commit."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal, Protocol, cast

from capability_agent._safe_files import open_bound_parent, read_bound_regular_file


@dataclass(frozen=True, slots=True)
class AnswerAdmissionInput:
    question: str
    answer_output: str
    result_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    guide_reads: tuple[tuple[str, str], ...] = ()
    authority_attempted: bool = False
    observed_capabilities: tuple[str, ...] = ()
    failed_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnswerAdmissionDecision:
    mode: Literal["authority_backed", "offline_information", "limited"]
    assurance: Literal["lineage_verified", "deterministic_information", "guide_access_verified", "limited"]
    answer_output: str
    diagnostic_codes: tuple[str, ...]


class AnswerAdmissionPolicy(Protocol):
    def admit(self, request: AnswerAdmissionInput) -> AnswerAdmissionDecision: ...


def aggregate_answer_admission(
    decisions: tuple[AnswerAdmissionDecision, ...], answer_output: str
) -> AnswerAdmissionDecision:
    """Conservatively summarize independently validated binding decisions."""
    pairs = {(decision.mode, decision.assurance) for decision in decisions}
    if len(pairs) == 1:
        mode, assurance = next(iter(pairs))
    else:
        mode, assurance = "limited", "limited"
    codes = tuple(dict.fromkeys(code for decision in decisions for code in decision.diagnostic_codes))
    return AnswerAdmissionDecision(
        cast(Literal["authority_backed", "offline_information", "limited"], mode),
        cast(Literal["lineage_verified", "deterministic_information", "guide_access_verified", "limited"], assurance),
        answer_output, codes,
    )


def read_answer_admission_metadata(
    answer_path: Path, *, expected_admission_ref: str | None = None
) -> AnswerAdmissionDecision | None:
    """Read a versioned sidecar, returning ``None`` for legacy answers.

    A sidecar is accepted only when it binds to the canonical digest of the
    adjacent immutable answer record.  Callers display ``unknown`` for None;
    corrupt or mismatched metadata is never silently trusted.
    """
    try:
        with open_bound_parent(answer_path) as (parent, answer_name):
            sidecar_bytes = read_bound_regular_file(parent, "answer-admission.json")
            if expected_admission_ref is None:
                raise ValueError(
                    "answer admission metadata has no durable commit binding"
                )
            answer_bytes = read_bound_regular_file(parent, answer_name)
    except FileNotFoundError:
        if expected_admission_ref is not None:
            raise ValueError("committed answer admission metadata is missing")
        return None
    except OSError as exc:
        raise ValueError("answer admission metadata is unreadable") from exc
    try:
        answer = json.loads(answer_bytes)
        payload = json.loads(sidecar_bytes)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("answer admission metadata is unreadable") from exc
    from capability_agent.trajectory.canonical import canonical_json_bytes

    expected_ref = "answer:sha256:" + sha256(canonical_json_bytes(answer)).hexdigest()
    actual_admission_ref = "admission:sha256:" + sha256(
        canonical_json_bytes(payload)
    ).hexdigest()
    if expected_admission_ref is not None and actual_admission_ref != expected_admission_ref:
        raise ValueError("answer admission metadata digest does not match its commit")
    if not isinstance(payload, dict) or payload.get("schema") not in {"capability-agent-answer-admission/1.0", "capability-agent-answer-admission/1.1", "capability-agent-answer-admission/1.2"}:
        raise ValueError("answer admission metadata schema is invalid")
    if payload.get("answer_ref") != expected_ref:
        raise ValueError("answer admission metadata does not match its answer")
    mode = payload.get("mode")
    assurance = payload.get("assurance")
    codes = payload.get("diagnostic_codes")
    if (
        mode not in {"authority_backed", "offline_information", "limited"}
        or assurance not in {"lineage_verified", "deterministic_information", "guide_access_verified", "limited"}
        or not isinstance(codes, list)
        or any(not isinstance(code, str) or not code for code in codes)
    ):
        raise ValueError("answer admission metadata is invalid")
    pairs = {
        ("authority_backed", "lineage_verified"),
        ("offline_information", "deterministic_information"),
        ("limited", "limited"),
    }
    if payload["schema"] != "capability-agent-answer-admission/1.0":
        pairs.add(("offline_information", "guide_access_verified"))
    if (mode, assurance) not in pairs:
        raise ValueError("answer admission metadata assurance is invalid")
    answer_output = answer.get("answer_output") if isinstance(answer, dict) else None
    if (
        not isinstance(answer_output, str)
        or payload.get("run_id") != answer.get("run_id")
        or payload.get("turn_id") != answer.get("turn_id")
    ):
        raise ValueError("answer record is invalid")
    decision = AnswerAdmissionDecision(
        cast(Literal["authority_backed", "offline_information", "limited"], mode),
        cast(Literal["lineage_verified", "deterministic_information", "guide_access_verified", "limited"], assurance),
        answer_output, tuple(codes),
    )
    if payload["schema"] == "capability-agent-answer-admission/1.2":
        bindings = payload.get("bindings")
        selected = answer.get("referenced_bindings")
        if (
            not isinstance(bindings, dict) or len(bindings) < 2
            or any(not isinstance(key, str) or not key for key in bindings)
            or not isinstance(selected, list)
            or (selected and (len(selected) != len(bindings) or set(selected) != set(bindings)))
        ):
            raise ValueError("answer admission binding metadata is invalid")
        decisions = []
        for entry in bindings.values():
            if not isinstance(entry, dict):
                raise ValueError("answer admission binding metadata is invalid")
            entry_mode, entry_assurance = entry.get("mode"), entry.get("assurance")
            entry_codes = entry.get("diagnostic_codes")
            if (
                not isinstance(entry_mode, str) or not isinstance(entry_assurance, str)
                or (entry_mode, entry_assurance) not in pairs
                or not isinstance(entry_codes, list)
                or any(not isinstance(code, str) or not code for code in entry_codes)
            ):
                raise ValueError("answer admission binding metadata is invalid")
            decisions.append(AnswerAdmissionDecision(
                cast(Literal["authority_backed", "offline_information", "limited"], entry_mode),
                cast(Literal["lineage_verified", "deterministic_information", "guide_access_verified", "limited"], entry_assurance),
                answer_output, tuple(entry_codes),
            ))
        aggregate = aggregate_answer_admission(tuple(decisions), answer_output)
        # Canonical JSON sorts object keys; diagnostic order follows submission order.
        if (aggregate.mode, aggregate.assurance) != (mode, assurance) or set(aggregate.diagnostic_codes) != set(codes):
            raise ValueError("answer admission aggregate does not match bindings")
    return decision

__all__ = [
    "AnswerAdmissionDecision",
    "AnswerAdmissionInput",
    "AnswerAdmissionPolicy",
    "aggregate_answer_admission",
    "read_answer_admission_metadata",
]
