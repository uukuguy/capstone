"""Domain-owned admission of a reader answer before its durable commit."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class AnswerAdmissionInput:
    question: str
    answer_output: str
    result_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnswerAdmissionDecision:
    mode: Literal["authority_backed", "offline_information", "limited"]
    assurance: Literal["lineage_verified", "deterministic_information", "limited"]
    answer_output: str
    diagnostic_codes: tuple[str, ...]


class AnswerAdmissionPolicy(Protocol):
    def admit(self, request: AnswerAdmissionInput) -> AnswerAdmissionDecision: ...


def read_answer_admission_metadata(
    answer_path: Path, *, expected_admission_ref: str | None = None
) -> AnswerAdmissionDecision | None:
    """Read a versioned sidecar, returning ``None`` for legacy answers.

    A sidecar is accepted only when it binds to the canonical digest of the
    adjacent immutable answer record.  Callers display ``unknown`` for None;
    corrupt or mismatched metadata is never silently trusted.
    """
    sidecar = answer_path.with_name("answer-admission.json")
    if sidecar.is_symlink() or answer_path.is_symlink():
        raise ValueError("answer admission metadata must not be a symlink")
    if not sidecar.exists():
        if expected_admission_ref is not None:
            raise ValueError("committed answer admission metadata is missing")
        return None
    try:
        if not stat.S_ISREG(os.stat(sidecar).st_mode) or not stat.S_ISREG(os.stat(answer_path).st_mode):
            raise ValueError("answer admission metadata must be regular files")
        answer = json.loads(answer_path.read_text(encoding="utf-8"))
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("answer admission metadata is unreadable") from exc
    from capability_agent.trajectory.canonical import canonical_json_bytes

    expected_ref = "answer:sha256:" + sha256(canonical_json_bytes(answer)).hexdigest()
    actual_admission_ref = "admission:sha256:" + sha256(
        canonical_json_bytes(payload)
    ).hexdigest()
    if expected_admission_ref is not None and actual_admission_ref != expected_admission_ref:
        raise ValueError("answer admission metadata digest does not match its commit")
    if not isinstance(payload, dict) or payload.get("schema") != "capability-agent-answer-admission/1.0":
        raise ValueError("answer admission metadata schema is invalid")
    if payload.get("answer_ref") != expected_ref:
        raise ValueError("answer admission metadata does not match its answer")
    mode = payload.get("mode")
    assurance = payload.get("assurance")
    codes = payload.get("diagnostic_codes")
    if (
        mode not in {"authority_backed", "offline_information", "limited"}
        or assurance not in {"lineage_verified", "deterministic_information", "limited"}
        or not isinstance(codes, list)
        or any(not isinstance(code, str) or not code for code in codes)
    ):
        raise ValueError("answer admission metadata is invalid")
    pairs = {
        ("authority_backed", "lineage_verified"),
        ("offline_information", "deterministic_information"),
        ("limited", "limited"),
    }
    if (mode, assurance) not in pairs:
        raise ValueError("answer admission metadata assurance is invalid")
    answer_output = answer.get("answer_output") if isinstance(answer, dict) else None
    if (
        not isinstance(answer_output, str)
        or payload.get("run_id") != answer.get("run_id")
        or payload.get("turn_id") != answer.get("turn_id")
    ):
        raise ValueError("answer record is invalid")
    return AnswerAdmissionDecision(mode, assurance, answer_output, tuple(codes))


__all__ = [
    "AnswerAdmissionDecision",
    "AnswerAdmissionInput",
    "AnswerAdmissionPolicy",
    "read_answer_admission_metadata",
]
