"""Application-owned compatibility execution for one grid question.

This module deliberately has no authority implementation knowledge.  It builds
the registered application and turns its immutable committed answer into the
legacy two-field delivery projection.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
from typing import Any, cast

from capability_agent.domain.execution import CapabilityExecutor

from capability_agent.application import ApplicationContextStore, ApplicationRequest, read_bound_regular_path
from capability_agent.runtime.catalog import ProviderCatalog
from capability_agent.runtime.models import CliLLMOptions

from grid_agent.application.composition import build_generic_application
from grid_agent.application.paths import ProjectPaths
from grid_agent.contracts import RunRequest
from grid_agent.knowledge.offline import answer_diagnostic
from grid_agent.compat.single_run_snapshot import publish_compatibility_snapshot


class SingleRunCompatibilityError(RuntimeError):
    """The application cannot safely publish a legacy single-run result."""


class SingleRunAdapter:
    """Run one question through the selected application and project its commit."""

    def __init__(
        self,
        *,
        project_paths: ProjectPaths,
        request: RunRequest,
        provider: str | None,
        model: str | None,
        base_url: str | None,
        api_key_env: str | None,
        environment: Mapping[str, str],
        semantic_event_observer: Callable[[Mapping[str, object]], None] | None = None,
        deterministic_offline: bool = False,
        application_builder: Callable[..., object] = build_generic_application,
    ) -> None:
        self._paths = project_paths
        self._request = request
        self._options = CliLLMOptions(
            provider=provider, model=model, base_url=base_url, api_key_env=api_key_env
        )
        self._environment = dict(environment)
        self._observe = semantic_event_observer
        self._deterministic_offline = deterministic_offline
        self._build = application_builder

    def run(self) -> str:
        """Return only the sidecar-bound answer after compatibility publication."""
        options: dict[str, object] = {
            "workspace_root": self._paths.runs_dir,
            "run_id": self._request.question_id,
            "cli_options": self._options,
            "environment": self._environment,
            "semantic_event_observer": self._observe,
        }
        if self._deterministic_offline:
            options["provider_factory"] = _deterministic_transport_factory
        else:
            options["provider_catalog"] = ProviderCatalog.load(
                self._paths.root / "configs/llm-providers.json"
            )
        application = self._build(
            "pandapower-static-analysis",
            **options,
        )
        runner = getattr(application, "run", None)
        if not callable(runner):
            raise SingleRunCompatibilityError("application runner is unavailable")
        outcome = runner(
            ApplicationRequest(
                application_id="pandapower-static-analysis",
                questions=(self._request.question,),
                run_id=self._request.question_id,
            )
        )
        if getattr(outcome, "status", None) != "completed":
            detail = getattr(outcome, "error", None)
            if not isinstance(detail, str) or not detail:
                detail = "application execution did not complete"
            raise SingleRunCompatibilityError(detail)
        workspace = self._paths.runs_dir / self._request.question_id
        answer = self.read_committed_answer(workspace, outcome)
        publish_compatibility_snapshot(workspace)
        return answer

    @staticmethod
    def read_committed_answer(workspace: Path, outcome: object) -> str:
        """Bind public text to one committed answer event and answer record.

        The event ledger is treated as an immutable declaration: ambiguous,
        unbound, or outside-turn answers fail closed instead of using rendered
        provider output.  Admission sidecars remain evaluation metadata; their
        absence or corruption must not replace a valid committed answer.
        """
        refs = getattr(getattr(outcome, "result", None), "core", None)
        answer_refs = getattr(refs, "answer_refs", ())
        run_id = getattr(refs, "run_id", None)
        if not isinstance(run_id, str) or run_id != workspace.name:
            raise SingleRunCompatibilityError("outcome run identity does not match workspace")
        if not isinstance(answer_refs, tuple) or len(answer_refs) != 1:
            raise SingleRunCompatibilityError("outcome has no unique committed answer")
        answer_ref = answer_refs[0]
        if not isinstance(answer_ref, str) or not answer_ref:
            raise SingleRunCompatibilityError("outcome answer reference is invalid")
        try:
            state, events = ApplicationContextStore.replay_events(
                workspace / "core" / "context-events.jsonl"
            )
        except Exception as exc:
            raise SingleRunCompatibilityError("committed answer ledger is unreadable") from exc
        if getattr(state, "run_id", None) != workspace.name:
            raise SingleRunCompatibilityError("committed answer ledger belongs to another run")
        submitted = [event for event in events if getattr(event, "event_type", None) == "answer.submitted"]
        if len(submitted) != 1:
            raise SingleRunCompatibilityError("committed answer event is missing or ambiguous")
        event = submitted[0]
        payload = getattr(event, "payload", None)
        turn_id = getattr(event, "turn_id", None)
        if not isinstance(payload, dict) or not isinstance(turn_id, str):
            raise SingleRunCompatibilityError("committed answer event is invalid")
        if payload.get("answer_ref") != answer_ref:
            raise SingleRunCompatibilityError("committed answer event is not bound to outcome")
        relative = payload.get("answer_path")
        expected_sha256 = payload.get("answer_sha256")
        if not isinstance(relative, str) or not isinstance(expected_sha256, str):
            raise SingleRunCompatibilityError("committed answer event lacks durable bindings")
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or not pure.parts or pure.parts[0] != "turns":
            raise SingleRunCompatibilityError("committed answer path is outside turns")
        if len(pure.parts) != 3 or pure.parts[1] != turn_id or pure.parts[2] != "answer.json":
            raise SingleRunCompatibilityError("committed answer path does not match its turn")
        answer_path = workspace.joinpath(*pure.parts)
        completed = [
            candidate for candidate in events
            if getattr(candidate, "event_type", None) == "turn.completed"
            and getattr(candidate, "turn_id", None) == turn_id
            and isinstance(getattr(candidate, "payload", None), dict)
            and candidate.payload.get("answer_ref") == answer_ref
            and candidate.payload.get("answer_path") == relative
            and candidate.payload.get("answer_sha256") == expected_sha256
        ]
        if len(completed) != 1:
            raise SingleRunCompatibilityError("committed answer completion is missing or ambiguous")
        try:
            answer_bytes = read_bound_regular_path(answer_path)
            answer = json.loads(answer_bytes)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SingleRunCompatibilityError("committed answer record is unreadable") from exc
        actual_sha256 = sha256(answer_bytes).hexdigest()
        if expected_sha256 != actual_sha256 or answer_ref != f"answer:sha256:{actual_sha256}":
            raise SingleRunCompatibilityError("committed answer record does not match its bindings")
        if (
            not isinstance(answer, dict)
            or answer.get("schema") != "capability-agent-answer/1.0"
            or answer.get("run_id") != workspace.name
            or answer.get("turn_id") != turn_id
            or not isinstance(answer.get("answer_output"), str)
        ):
            raise SingleRunCompatibilityError("committed answer record is invalid")
        return answer["answer_output"]

__all__ = ["SingleRunAdapter", "SingleRunCompatibilityError"]


def _deterministic_transport_factory(*, bindings: Mapping[str, object], catalog: object, **_kwargs: object) -> object:
    binding = bindings.get("grid")
    executor = getattr(getattr(binding, "runtime", None), "executor", None)
    if not callable(getattr(executor, "invoke", None)):
        raise SingleRunCompatibilityError("prepared grid executor is unavailable")
    return _DeterministicDiagnosticTransport(cast(CapabilityExecutor, executor), catalog)


class _DeterministicDiagnosticTransport:
    """Provider-shaped transport that emits every real executor call semantically."""

    def __init__(self, executor: CapabilityExecutor, catalog: object | None = None) -> None:
        self._executor = executor
        self._catalog = catalog
        self._sequence = 0

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def prompt_and_wait(
        self, question: str, *, on_semantic_event: Callable[..., None], **_kwargs: object
    ) -> str:
        transport = self

        class Client:
            def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
                transport._sequence += 1
                call_id = f"offline-{transport._sequence}"
                key = {"binding_id": "grid", "capability_id": capability}
                tool = next(
                    (
                        candidate
                        for candidate in getattr(transport._catalog, "domain_tools", ())
                        if getattr(getattr(candidate, "key", None), "binding_id", None) == "grid"
                        and getattr(getattr(candidate, "key", None), "capability_id", None) == capability
                    ),
                    None,
                )
                tool_name = getattr(tool, "name", None)
                projector_id = getattr(tool, "projector_id", None)
                if not isinstance(tool_name, str) or not tool_name or not isinstance(projector_id, str) or not projector_id:
                    raise SingleRunCompatibilityError(
                        "offline capability is not published by the prepared catalog"
                    )
                on_semantic_event(
                    {"type": "tool_execution_start", "toolCallId": call_id,
                     "toolName": tool_name, "capability_key": key, "capability": capability,
                     "args": arguments}, transport._sequence
                )
                result = transport._executor.invoke(capability, arguments)
                if not isinstance(result, dict):
                    raise SingleRunCompatibilityError("prepared grid executor returned invalid result")
                on_semantic_event(
                    {"type": "tool_result", "toolCallId": call_id, "toolName": tool_name,
                     "capability_key": key, "capability": capability, "ok": True,
                     "result": result, "projector_id": projector_id,
                     "evidence_refs": result.get("evidence_refs", [])},
                    transport._sequence,
                )
                return result

        return answer_diagnostic(question, Client())
