"""Provider-free Thread host used by the M5 contract matrix.

The adapter is deliberately validation-owned.  It supplies a deterministic
Pi-compatible prompt session to the production ``PreparedKernelPiSessionFactory``;
the Thread service, Harness runner, Domain Pack admission policy, and Authority
executors remain the same code used by a hosted process.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient

from capstone_agent.host_api import create_host_app
from capstone_agent.ledger import Ledger
from capstone_agent.kernel_capability_preparation import AuthorityModelBinding
from capstone_agent.thread_application import ThreadApplicationAssembly
from capstone_agent.thread_service import InMemoryThreadService
from capstone_agent.thread_protocol import ThreadSnapshot
from capstone_agent.thread_worker import run_pending_attempt
from capstone_agent.session import WorkerRegistry
from capstone_model_capability_spi import ModelCapabilitySelection

from .http_runner import HttpThreadSession


from .scripted_session import _ScriptedPiSession, _refs, _load_pandapower_questions, _load_pypsa_case


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


class _Ledger(Ledger):
    def __init__(self) -> None:
        pass

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
            def binder(prepared: Any, context: Any) -> AuthorityModelBinding:
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
        from pypsa_agent.thread_binding import verify_bound_model_reference
        catalog = RegisteredPyPSAThreadCatalog()
        def resolver(model_id: str) -> Mapping[str, object]:
            descriptor = catalog.resolve(model_id)
            return {"model_id": descriptor.model_id, "revision_ref": descriptor.model_revision, "implementation_family": descriptor.implementation_family, "authority_model_ref": descriptor.authority_model_ref, "display_name": descriptor.display_name, "diagram_provider_id": descriptor.diagram_provider_id}
        def binder(prepared: Any, context: Any) -> AuthorityModelBinding:
            binding = prepared.bindings["source"]
            opened = binding.runtime.executor.invoke("model.open", {"catalog_id": context.model_id})
            model_ref = opened["model_ref"]
            return AuthorityModelBinding(
                "source", context.model_id, context.model_revision,
                context.implementation_family, model_ref,
                model_reference_verifier=lambda reference: verify_bound_model_reference(
                    binding.runtime.authority, reference,
                    model_id=context.model_id, base_ref=model_ref,
                ),
            )
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
