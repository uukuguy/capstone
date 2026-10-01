"""Provider-free Thread host used by the M5 contract matrix.

The adapter is deliberately validation-owned.  It supplies a deterministic
Pi-compatible prompt session to the production ``PreparedKernelPiSessionFactory``;
the Thread service, Harness runner, Domain Pack admission policy, and Authority
executors remain the same code used by a hosted process.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient

from capability_agent.application.context_store import ApplicationContextStore
from capstone_agent.host_api import create_host_app
from capstone_agent.kernel_capability_preparation import AuthorityModelBinding, PreparedKernelApplicationProfile
from capstone_agent.kernel_pi_session import _build_kernel_admission
from capstone_agent.thread_application import ThreadApplicationAssembly
from capstone_agent.thread_service import InMemoryThreadService
from capstone_agent.thread_protocol import ThreadSnapshot
from capstone_agent.thread_worker import run_pending_attempt
from capstone_agent.session import WorkerRegistry
from capability_agent.tools.catalog import BoundDomainCatalog, CompositeToolCatalog, CoreToolCatalog
from capstone_model_capability_spi import ModelCapabilitySelection

from .http_runner import HttpThreadSession


ROOT = Path(__file__).resolve().parents[2]
PANDAPOWER_CASE = ROOT / "validation" / "application" / "pandapower-scripted-task.json"
PYPSA_CASES = ROOT / "validation" / "pypsa-cases" / "cases.json"


def _refs(result: Mapping[str, object]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    result_refs: list[str] = []
    evidence_refs: list[str] = []
    explicit = result.get("result_ref")
    if isinstance(explicit, str) and explicit:
        result_refs.append(explicit)
    explicit_many = result.get("result_refs")
    if isinstance(explicit_many, (list, tuple)):
        result_refs.extend(ref for ref in explicit_many if isinstance(ref, str) and ref)
    evidence_one = result.get("evidence_ref")
    if isinstance(evidence_one, str) and evidence_one:
        evidence_refs.append(evidence_one)
    evidence = result.get("evidence_refs")
    if isinstance(evidence, (list, tuple)):
        evidence_refs.extend(ref for ref in evidence if isinstance(ref, str) and ref)
    return tuple(dict.fromkeys(result_refs)), tuple(dict.fromkeys(evidence_refs))


def _load_pandapower_questions() -> tuple[dict[str, object], ...]:
    document = json.loads(PANDAPOWER_CASE.read_text(encoding="utf-8"))
    questions = document.get("questions")
    if not isinstance(questions, list):
        raise ValueError("pandapower validation case questions are invalid")
    return tuple(item for item in questions if isinstance(item, dict))


def _load_pypsa_case() -> dict[str, object]:
    document = json.loads(PYPSA_CASES.read_text(encoding="utf-8"))
    cases = document.get("cases")
    if not isinstance(cases, list):
        raise ValueError("PyPSA validation case catalog is invalid")
    case = next((item for item in cases if isinstance(item, dict) and item.get("status") == "runnable"), None)
    if case is None:
        raise ValueError("PyPSA has no runnable validation case")
    return case


class _ScriptedPiSession:
    """A deterministic prompt session that invokes only prepared semantic tools."""

    def __init__(self, claim, profiles: tuple[PreparedKernelApplicationProfile, ...], *, family: str, state: dict[str, object] | None = None) -> None:
        if len(profiles) != 1:
            raise ValueError("M5 provider-free session expects one prepared profile")
        profile = profiles[0]
        prepared = profile.prepared_application
        bindings = getattr(prepared, "bindings", None)
        if not isinstance(bindings, Mapping):
            raise ValueError("prepared bindings are unavailable")
        self._claim = claim
        self._family = family
        self._state = state if state is not None else {}
        self._prepared = prepared
        self._bindings = bindings
        self._admission = _build_kernel_admission(profiles)
        domains = tuple(BoundDomainCatalog.from_prepared(binding) for binding in bindings.values())
        self._catalog = CompositeToolCatalog.build(
            core=CoreToolCatalog.default(namespace="agent_"), domains=domains,
        )
        self._tools = {tool.key.capability_id: tool for tool in self._catalog.domain_tools}
        self._context_ref: str | None = self._state.get("context_ref") if isinstance(self._state.get("context_ref"), str) else None
        self._model_ref: str | None = self._state.get("model_ref") if isinstance(self._state.get("model_ref"), str) else None
        self._result_ref: str | None = self._state.get("result_ref") if isinstance(self._state.get("result_ref"), str) else None
        self._evidence_ref: str | None = self._state.get("evidence_ref") if isinstance(self._state.get("evidence_ref"), str) else None
        self._turn_index = int(self._state.get("turn_index", 0))
        self._started = False
        self._stopped = False
        self._calls: list[Mapping[str, object]] = []
        self._instructions = self._build_instructions()
        self._handoff = None
        if family == "pypsa":
            from capability_agent.application.reference_handoff import ReferenceHandoffService
            cached_handoff = self._state.get("handoff")
            if cached_handoff is not None:
                self._handoff = cached_handoff
            else:
                store = ApplicationContextStore.initialize(profile.workspace)
                self._handoff = ReferenceHandoffService(
                    profile.profile, profile.workspace, store, bindings,
                )
                self._state["handoff"] = self._handoff

    def _build_instructions(self) -> tuple[tuple[str, tuple[Mapping[str, object], ...]], ...]:
        if self._family == "pandapower":
            document = _load_pandapower_questions()
            return tuple((str(item["text"]), tuple(step for step in item.get("steps", ()) if isinstance(step, Mapping))) for item in document)
        case = _load_pypsa_case()
        intro = case.get("introduction")
        question = case.get("question")
        workflow = case.get("workflow")
        if not isinstance(intro, Mapping) or not isinstance(question, str) or not isinstance(workflow, list):
            raise ValueError("PyPSA validation case shape is invalid")
        steps = tuple({"capability": item} for item in workflow if isinstance(item, str))
        return ((question, steps),)

    def start(self) -> None:
        if self._stopped:
            raise RuntimeError("provider-free Pi session cannot restart")
        self._started = True

    def stop(self) -> None:
        self._stopped = True

    def admit_attempt(self, claim, answer, result_refs, evidence_refs, tool_events):
        return self._admission(claim, answer, result_refs, evidence_refs, tool_events)

    def prompt_and_wait(
        self, question: str, *, on_semantic_event: Callable[[Mapping[str, object]], None],
        correlation_id: str | None, on_heartbeat: Callable[[], None],
    ) -> str:
        if not self._started or self._stopped:
            raise RuntimeError("provider-free Pi session is not running")
        if not isinstance(correlation_id, str) or not correlation_id:
            raise ValueError("Attempt correlation ID is missing")
        if self._claim.turn_plan is not None and self._claim.turn_plan.route == "ordinary":
            on_heartbeat()
            return "你好，我可以围绕当前登记的电网模型进行普通说明，也可以执行有证据的专业分析。"
        if self._turn_index >= len(self._instructions):
            raise ValueError("validation instruction sequence is exhausted")
        expected, steps = self._instructions[self._turn_index]
        if question != expected:
            raise ValueError("registered validation instruction changed")
        on_heartbeat()
        for step in steps:
            capability = step.get("capability")
            if not isinstance(capability, str) or capability not in self._tools:
                raise ValueError(f"validation capability is not published: {capability}")
            arguments = self._arguments(capability, step.get("arguments"))
            self._invoke(capability, arguments, correlation_id, on_semantic_event)
            if capability == "result.branches.rank" and self._evidence_ref is not None:
                # A derived ranking returns the source result reference. Retrieve
                # its persisted evidence explicitly so professional admission can
                # cite an Authority-declared evidence reference in this Attempt.
                self._invoke(
                    "evidence.get", {"evidence_ref": self._evidence_ref},
                    correlation_id, on_semantic_event,
                )
            on_heartbeat()
        self._turn_index += 1
        self._state.update({
            "turn_index": self._turn_index,
            "context_ref": self._context_ref,
            "model_ref": self._model_ref,
            "result_ref": self._result_ref,
            "evidence_ref": self._evidence_ref,
        })
        return self._answer()

    def _arguments(self, capability: str, raw: object) -> dict[str, object]:
        arguments = dict(raw) if isinstance(raw, Mapping) else {}
        for key, value in tuple(arguments.items()):
            if value == "$context_ref":
                arguments[key] = self._context_ref
            elif value == "$result_ref":
                arguments[key] = self._result_ref
        if self._family == "pypsa":
            if capability == "model.open":
                case = _load_pypsa_case()
                arguments = {"catalog_id": case["model_id"]}
            elif capability == "model.derive_series":
                case = _load_pypsa_case()
                scenario = case["scenario"]
                arguments = {
                    "model_ref": self._model_ref, "load_id": scenario["load_id"],
                    "p_set_mw": scenario["variant_mw"],
                }
            elif capability.startswith("model."):
                arguments = {"model_ref": self._model_ref}
            elif capability == "operations.dispatch":
                if self._handoff is None or self._model_ref is None:
                    raise RuntimeError("PyPSA operation handoff is unavailable")
                receipt = self._handoff.prepare_handoff(
                    source_binding_id="source", target_binding_id="operations",
                    reference=self._model_ref, reference_kind="model", purpose="operations",
                    capability=capability,
                )
                arguments = {"reference": self._model_ref, "handoff_ref": receipt.receipt_ref}
        return arguments

    def _invoke(self, capability: str, arguments: dict[str, object], turn_id: str, callback: Callable[[Mapping[str, object]], None]) -> None:
        tool = self._tools[capability]
        binding_id = tool.key.binding_id
        event_base = {
            "call_id": f"m5-{self._claim.attempt.attempt_id}-{len(self._calls) + 1}",
            "tool_name": tool.name, "capability": capability,
            "capability_key": {"binding_id": binding_id, "capability_id": capability},
            "run_id": self._claim.run_id, "turn_id": turn_id,
        }
        callback({**event_base, "type": "tool_execution_start", "arguments": arguments})
        executor = getattr(getattr(self._bindings[binding_id], "endpoint", None), "executor", None)
        invoke = getattr(executor, "invoke", None)
        if not callable(invoke):
            raise RuntimeError("prepared Authority endpoint is unavailable")
        result = invoke(capability, arguments)
        if not isinstance(result, Mapping):
            raise RuntimeError("Authority tool returned a non-object")
        result = dict(result)
        result_refs, evidence_refs = _refs(result)
        callback({
            **event_base, "type": "tool_result", "ok": True, "result": result,
            "result_refs": list(result_refs), "evidence_refs": list(evidence_refs),
            "projector_id": "m5-provider-free-v1",
            "result_kind": f"{self._family}.validation.result",
        })
        self._calls.append({"capability": capability, "result": result})
        if capability == "context.open":
            self._context_ref = result.get("context_ref") if isinstance(result.get("context_ref"), str) else self._context_ref
        if capability == "model.open":
            self._model_ref = result.get("model_ref") if isinstance(result.get("model_ref"), str) else self._model_ref
        if isinstance(result.get("result_ref"), str):
            self._result_ref = result["result_ref"]
        if evidence_refs:
            self._evidence_ref = evidence_refs[0]

    def _answer(self) -> str:
        if self._family == "pandapower":
            return "已完成登记的 pandapower 分析步骤；结果和本轮证据已通过 Authority 准入。"
        return "已完成登记的 PyPSA 分析；模型修订、计算结果和本轮证据已通过 Authority 准入。"


class _BootstrapService(InMemoryThreadService):
    """Single-thread in-memory service that accepts the first creator write."""

    def __init__(self) -> None:
        super().__init__(ThreadSnapshot.from_document({
            "schema": "capstone-thread-snapshot/1", "thread_id": "thr_bootstrap",
            "run": {"run_id": "run_bootstrap", "state": "open"},
            "active_model_context": {
                "id": "ctx_bootstrap", "model_id": "ieee39",
                "model_revision": "revision:sha256:" + "0" * 64,
                "implementation_family": "pandapower", "selection_revision": "sel_0",
            }, "active_grid_page_id": "page_ieee39", "current_attempt": None,
            "last_event_seq": 0, "base_event_seq": 0,
        }))

    def create_thread(self, snapshot):
        with self._lock:
            if self._snapshot.thread_id != "thr_bootstrap":
                raise ValueError("in-memory provider-free host already has a thread")
            self._snapshot = snapshot
            return snapshot


class _Ledger:
    def ping(self) -> bool:
        return True


class _AppTransport(httpx.BaseTransport):
    def __init__(self, client: TestClient) -> None:
        self._client = client

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self._client.request(
            request.method, str(request.url), headers=dict(request.headers), content=request.content,
        )
        return httpx.Response(
            response.status_code, headers=dict(response.headers), content=response.content,
            request=request,
        )


class _ProviderFreeSession(HttpThreadSession):
    def __init__(self, host: "ProviderFreeThreadHost", *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._host = host

    def command(self, *args: Any, **kwargs: Any):
        receipt = super().command(*args, **kwargs)
        if receipt.status == "accepted":
            self._host.run_one()
        return receipt


class ProviderFreeThreadHost:
    """Run one selected registered Authority through the real Thread HTTP path."""

    def __init__(self, application_id: str, root: Path) -> None:
        if application_id not in {"pandapower-static-analysis", "pypsa-business-cases"}:
            raise ValueError("M5 provider-free application is not registered")
        self.application_id = application_id
        # ApplicationWorkspace rejects symlinked ancestors; macOS temporary
        # directories are commonly exposed through /var -> /private/var.
        self.root = root.resolve()
        self.service = _BootstrapService()
        self._worker_id = f"m5-{application_id}"
        self._session_state: dict[str, object] = {}
        self._assembly = self._build_assembly()
        self._creator = self._assembly.thread_creator(self.service)
        self._client: TestClient | None = None
        self.session: HttpThreadSession | None = None

    def _build_assembly(self) -> ThreadApplicationAssembly:
        if self.application_id == "pandapower-static-analysis":
            from grid_simulator.engine import Pandapower340Engine
            from grid_simulator.models import ModelRegistry
            from grid_agent.application.thread_capabilities import build_pandapower_thread_application
            from grid_agent.application.thread_capabilities import PANDAPOWER_PROFILE_DESCRIPTOR

            models = ModelRegistry(Pandapower340Engine())
            def resolver(model_id: str) -> Mapping[str, object]:
                model = models.get(model_id)
                return {"model_id": model.model_id, "revision_ref": models.trusted_revision_ref(model.model_id), "implementation_family": model.engine, "authority_model_ref": f"pandapower:{model.model_id}", "display_name": model.model_id, "diagram_provider_id": "pandapower"}
            def binder(prepared: object, context: Any) -> AuthorityModelBinding:
                binding = prepared.bindings["grid"]
                opened = binding.runtime.executor.invoke("context.open", {"model_id": context.model_id})
                return AuthorityModelBinding("grid", context.model_id, opened["revision_ref"], context.implementation_family, opened["context_ref"])
            def builder(claim, context, profiles):
                return _ScriptedPiSession(claim, profiles, family="pandapower", state=self._session_state)
            return build_pandapower_thread_application(
                default_model_id="ieee39", model_resolver=resolver,
                workspace_root=self.root / "pandapower", model_binder=binder,
                session_builder=builder,
                default_selection=ModelCapabilitySelection((PANDAPOWER_PROFILE_DESCRIPTOR.reference,)),
            )
        from pypsa_agent.thread_capabilities import build_pypsa_thread_application, PYPSA_PROFILE_DESCRIPTOR
        from pypsa_agent.hosted import RegisteredPyPSAThreadCatalog
        catalog = RegisteredPyPSAThreadCatalog()
        def resolver(model_id: str) -> Mapping[str, object]:
            descriptor = catalog.resolve(model_id)
            return {"model_id": descriptor.model_id, "revision_ref": descriptor.model_revision, "implementation_family": descriptor.implementation_family, "authority_model_ref": descriptor.authority_model_ref, "display_name": descriptor.display_name, "diagram_provider_id": descriptor.diagram_provider_id}
        def binder(prepared: object, context: Any) -> AuthorityModelBinding:
            binding = prepared.bindings["source"]
            opened = binding.runtime.executor.invoke("model.open", {"catalog_id": context.model_id})
            return AuthorityModelBinding("source", context.model_id, context.model_revision, context.implementation_family, opened["model_ref"])
        def builder(claim, context, profiles):
            return _ScriptedPiSession(claim, profiles, family="pypsa", state=self._session_state)
        return build_pypsa_thread_application(
            default_model_id=catalog.default_model_id, model_resolver=resolver,
            workspace_root=self.root / "pypsa", model_binder=binder,
            session_builder=builder,
            default_selection=ModelCapabilitySelection((PYPSA_PROFILE_DESCRIPTOR.reference,)),
        )

    def __enter__(self) -> HttpThreadSession:
        app = create_host_app(
            _Ledger(), WorkerRegistry(()), operator_token="m5-provider-free-token",
            allowed_hosts={"testserver", "localhost"}, allowed_origins={"http://testserver"},
            thread_service=self.service, thread_application=self._assembly,
        )
        self._client = TestClient(app)
        self._client.__enter__()
        self.session = _ProviderFreeSession(
            self,
            "http://testserver", "m5-provider-free-token",
            client=httpx.Client(transport=_AppTransport(self._client), base_url="http://testserver"),
        )
        return self.session

    def run_one(self) -> None:
        run_pending_attempt(
            self.service, self._assembly.runtime_factory,
            worker_id=self._worker_id, turn_router=self._assembly.turn_router_for_worker(),
        )

    def __exit__(self, *_: object) -> None:
        if self.session is not None:
            self.session.close()
        if self._client is not None:
            self._client.__exit__(None, None, None)


__all__ = ["ProviderFreeThreadHost"]
