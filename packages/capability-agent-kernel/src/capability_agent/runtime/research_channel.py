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
from capability_agent.application.context_store import ContextUpdateRejected
from capability_agent.application.research_models import research_depth_tool_schema, research_tool_schemas, task_progress_tool_schema
from capability_agent.runtime.capacity import runtime_limits as resolve_limits, CapacityExceeded, check_capacity, observe_capacity, runtime_limit_mode
from capability_agent.application.research_models import _check_research_capacity
from capability_agent.application.context_reducer import ContextTransitionError

_IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class ResearchRequestChannel:
    """Serve a bounded batch during RPC waits and publish views before receipts."""

    def __init__(self, controller: ResearchController, *, attempt_id: str,
                 is_active: Callable[[], bool], channel_root: Path | None = None, runtime_limits=None) -> None:
        if not _IDENTITY.fullmatch(attempt_id):
            raise ValueError("invalid research attempt identity")
        self.controller = controller
        self.attempt_id = attempt_id
        self.is_active = is_active
        self.runtime_limits = resolve_limits(controller.runtime_limits if runtime_limits is None else runtime_limits)
        if dict(self.runtime_limits) != dict(controller.runtime_limits):
            raise ValueError('research controller and channel runtime_limits differ')
        self.root = ensure_bound_directory(channel_root if channel_root is not None
            else controller.store.workspace.core_path / "research" / attempt_id)
        self.requests_path = ensure_bound_directory(self.root / "requests")
        self.receipts_path = ensure_bound_directory(self.root / "receipts")
        self.view_path = self.root / "view.json"
        read_schema, update_schema = research_tool_schemas(self.runtime_limits)
        self._write(self.root / "binding.json", {
            "schema_version": "capability-research-channel/1.0",
            "run_id": controller.store.snapshot.run_id,
            "turn_id": controller.turn_id,
            "attempt_id": attempt_id,
            "research_id": controller.research_id,
            "read_tool_schema": read_schema,
            "update_tool_schema": update_schema,
            "depth_tool_schema": research_depth_tool_schema(),
            "progress_tool_schema": task_progress_tool_schema(self.runtime_limits),
            "runtime_limits": dict(self.runtime_limits),
            "runtime_limit_mode": runtime_limit_mode(),
        })
        self.publish_view()

    def publish_view(self) -> None:
        state = self.controller.read()
        self._write(self.view_path, self._view_document(state))

    def _view_document(self,state):
        return {
            "schema_version": "capability-research-view/1.0",
            "run_id": self.controller.store.snapshot.run_id,
            "turn_id": self.controller.turn_id,
            "attempt_id": self.attempt_id,
            "research_id": self.controller.research_id,
            "research_revision": state.revision if state else 0,
            "state": state.model_dump(mode="json") if state else None,
        }

    def drain(self, *, max_requests: int | None = None) -> int:
        max_requests = self.runtime_limits['rpc_batch_requests'] if max_requests is None else max_requests
        if type(max_requests) is not int or max_requests < 1:
            raise ValueError('research batch must contain positive request count')
        check_capacity(self.runtime_limits, 'rpc_batch_requests', max_requests, unit='requests', phase='research_drain')
        handled = 0
        for path in sorted(self.requests_path.glob("*.json")):
            request_id = path.stem
            if not _IDENTITY.fullmatch(request_id):
                raise RuntimeError("invalid research request filename")
            raw = read_bound_regular_path(path)
            digest = sha256(raw).hexdigest()
            ack_path = self.receipts_path / path.name
            if ack_path.exists() or ack_path.is_symlink():
                ack = json.loads(read_bound_regular_path(ack_path))
                if ack.get("request_sha256") != digest:
                    raise RuntimeError("research request changed after receipt")
                if ack.get("status") != "not_confirmed":
                    continue
            try:
                check_capacity(self.runtime_limits, 'research_request_bytes', len(raw), unit='bytes', phase='research_request')
                ack = self._process(raw, request_id)
            except CapacityExceeded as error:
                if error.mode == 'debug':
                    raise
                ack = {'status': 'rejected', **error.document()}
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
        with self.controller.store.research_transaction():
            return self._process_request(raw, request_id)

    def _process_request(self, raw: bytes, request_id: str) -> dict[str, object]:
        try:
            document = json.loads(raw)
            if isinstance(document, dict):
                _check_research_capacity(document.get('changes', {}), self.runtime_limits)
            request = ResearchUpdate.model_validate_json(raw, context={'runtime_limits': self.runtime_limits})
            if request.request_id != request_id:
                return {"status": "rejected", "code": "request_identity_mismatch"}
        except CapacityExceeded as error:
            if error.mode == 'debug':
                raise
            return {'status': 'rejected', **error.document()}
        except ValidationError as exc:
            errors = exc.errors(include_input=False, include_context=False, include_url=False)
            self._diagnostic_bound('diagnostic_error_count',len(errors),'items')
            return {"status": "rejected", "code": "invalid_research_update",
                    "validation_errors": [{"path": self._diagnostic_path(error['loc']), "code": error["type"],
                        "message": self._diagnostic_text(str(error["msg"])) if error["type"] != "json_invalid"
                        else "Request must be a valid JSON object"} for error in errors[:self.runtime_limits['diagnostic_error_count']]],
                    "validation_errors_truncated": len(errors) > self.runtime_limits['diagnostic_error_count']}
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
                for index, ref in enumerate(request.changes.references(), start=1):
                    if not self.controller.admit_reference(ref):
                        return {"status": "rejected", "code": "research_reference_not_admitted",
                                "rejected_reference": ref,
                                "message": f"Source reference {index} was not admitted for this attempt. "
                                "No update was committed. Use references from successful tool receipts; "
                                "keep unsupported claims as hypotheses."}
                candidate=self._view_document(self.controller.preview(document))
                check_capacity(self.runtime_limits,'research_response_bytes',len((json.dumps(candidate,ensure_ascii=False,sort_keys=True)+'\n').encode()),unit='bytes',phase='research_response')
                committed = self.controller.update(document)
        except CapacityExceeded as error:
            if error.mode == 'debug':
                raise
            return {'status': 'rejected', **error.document()}
        except (ContextUpdateRejected,ContextTransitionError) as exc:
            return {"status": "rejected", "code": "research_state_update_rejected",
                    "message": self._diagnostic_text(str(exc)) + ". No update was committed; existing research records are retained."}
        except ContextStoreError:
            # A storage failure can have an uncertain outcome. Never label it a rollback.
            return {"status": "not_confirmed", "code": "research_update_not_confirmed"}
        self.publish_view()
        return {"status": "committed", "receipt": committed.model_dump(mode="json")}

    def _diagnostic_bound(self, dimension, actual, unit):
        observe_capacity(dimension,actual,limits=self.runtime_limits,unit=unit,phase='research_diagnostic')

    def _diagnostic_text(self, text, dimension='diagnostic_text_chars'):
        self._diagnostic_bound(dimension,len(text),'characters')
        return text[:self.runtime_limits[dimension]]

    def _diagnostic_path(self, parts):
        self._diagnostic_bound('diagnostic_path_parts',len(parts),'items')
        return [self._diagnostic_text(part,'diagnostic_path_chars') if isinstance(part,str) else part
                for part in parts[:self.runtime_limits['diagnostic_path_parts']]]

    def _write(self, path: Path, document: dict[str, object]) -> None:
        text = json.dumps(document, ensure_ascii=False, sort_keys=True) + '\n'
        check_capacity(self.runtime_limits, 'research_response_bytes', len(text.encode()), unit='bytes', phase='research_response')
        write_bound_text(path, text)
