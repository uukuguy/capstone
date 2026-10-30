"""Authenticated, stateless HTTP and SSE adapter over the durable ledger."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from urllib.parse import quote
from collections.abc import Callable, Iterator, Mapping

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.concurrency import run_in_threadpool
from capstone_agent.thread_startup_timing import record_thread_startup

from capstone_agent.artifacts import ArtifactService
from capstone_agent.catalog import build_catalog
from capstone_agent.case_diagrams import CaseDiagramCache, load_case_diagram
from capstone_agent.case_service import CaseExecutionService
from capstone_agent.ledger import Conflict, Ledger, SessionRecord
from capstone_agent.server import _CreateSession, _TurnInput
from capstone_agent.session import WorkerRegistry, WorkerSession, WorkerSpec
from capstone_agent.thread_application import ThreadApplicationAssembly
from capstone_agent.thread_streams import ThreadStreamBudget
from capstone_agent.thread_protocol import ThreadProtocolError
from capstone_agent.workspace_scope import DEFAULT_WORKSPACE, WORKSPACE_HEADER, workspace_header
from capstone_agent.thread_service import (
    ThreadCreator,
    ThreadExecutionError,
    ThreadNotFound,
    ThreadProtocolUpgradeRequired,
    ThreadResyncRequired,
    ThreadService,
)


def _status(record: SessionRecord) -> dict[str, object]:
    return {
        "session_id": record.session_id, "run_id": record.run_id,
        "application_id": record.application_id, "state": record.state,
        "error_code": record.error_code,
        "accepted_turns": record.accepted_turns,
        "completed_turns": record.completed_turns,
    }


def create_host_app(
    ledger: Ledger, registry: WorkerRegistry, *, operator_token: str,
    allowed_hosts: set[str], allowed_origins: set[str],
    public_demo: bool = False,
    thread_open_access: bool = False,
    public_provider: str | None = None,
    public_model: str | None = None,
    repo_root: Path | None = None,
    artifacts: ArtifactService | None = None,
    preview_loader: Callable[[WorkerSpec, str], dict[str, object]] | None = None,
    wake_worker: Callable[[], object] | None = None,
    prepare_workers: Callable[[], Iterator[Mapping[str, str]]] | None = None,
    prepare_model: Callable[[str, str], bool] | None = None,
    thread_service: ThreadService | None = None,
    thread_creator: ThreadCreator | None = None,
    thread_application: ThreadApplicationAssembly | None = None,
    case_service: CaseExecutionService | None = None,
    validation_status: Callable[[], Mapping[str, object]] | None = None,
    native_artifact_executor=None,
    capacity_profile=None,
) -> FastAPI:
    from .application_capacity import initialize_capacity, current_capacity, limits, CapacityExceeded
    if capacity_profile is not None:
        initialize_capacity(capacity_profile)
    if len(operator_token) < 8 or not allowed_hosts or not allowed_origins:
        raise ValueError("host access configuration is invalid")
    if thread_application is not None:
        if thread_creator is not None:
            raise ValueError("thread_application cannot be combined with thread_creator")
        if thread_service is None:
            raise ValueError("thread_service is required for thread_application")
        thread_creator = thread_application.thread_creator(thread_service)
    if case_service is not None and (
        thread_service is None or case_service.thread_service is not thread_service
    ):
        raise ValueError("case_service must use the configured thread_service")
    demo_token = (hmac.new(operator_token.encode(), b"capstone-public-demo-v1",
                           hashlib.sha256).hexdigest() if public_demo else None)
    catalog = build_catalog(registry, repo_root or Path(__file__).resolve().parents[4])
    public_cases = frozenset(
        (application["application_id"], case["case_id"])
        for application in catalog["applications"]
        for case in application["cases"]
    )
    diagram_cases = {
        (application["application_id"], case["case_id"]): registry.resolve(application["application_id"])
        for application in catalog["applications"] for case in application["cases"]
        if preview_loader is not None or registry.resolve(application["application_id"]).preview_command
    }
    diagrams = CaseDiagramCache(diagram_cases, preview_loader or load_case_diagram)
    last_wake = float('-inf')
    wake_lock = threading.Lock()

    def request_model_preparation(thread_id: str, family: str | None = None) -> None:
        if prepare_model is None:
            return
        started = time.perf_counter()
        try:
            if family is None:
                if thread_service is None:
                    return
                context = thread_service.snapshot(thread_id).active_model_context
                if context is None:
                    return
                family = context.implementation_family
            if not prepare_model(thread_id, family):
                logging.getLogger(__name__).warning('Model preparation incomplete for thread %s', thread_id)
        except Exception:
            logging.getLogger(__name__).warning('Model preparation unavailable for thread %s', thread_id)
        finally:
            record_thread_startup(thread_id, 'model_prepare_request', started)

    def request_worker(session_id: str, *, force: bool = False) -> None:
        nonlocal last_wake
        if wake_worker is None:
            return
        with wake_lock:
            if not force and time.monotonic() - last_wake < 2:
                return
        try:
            result = wake_worker()
        except (OSError, TimeoutError):
            return
        if result is not False:
            with wake_lock:
                last_wake = time.monotonic()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        diagrams.prewarm()
        try:
            yield
        finally:
            diagrams.close()

    app = FastAPI(title="capstone-agent", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    @app.exception_handler(CapacityExceeded)
    async def capacity_error(_request, error):
        return JSONResponse(status_code=413, content={'detail': error.to_document()})
    app.add_middleware(ThreadStreamBudget,
                       max_streams=int(os.environ.get('CAPSTONE_THREAD_MAX_STREAMS') or str(limits.thread_stream_count)),
                       per_thread=int(os.environ.get('CAPSTONE_THREAD_STREAMS_PER_THREAD') or str(limits.thread_streams_per_thread)))

    @app.middleware("http")
    async def access(request: Request, call_next):
        request.state.public_demo = False
        thread_resource = (request.url.path == '/api/v1/threads'
                           or request.url.path.startswith('/api/v1/threads/'))
        versioned_resource = thread_resource or request.url.path == '/api/v1/workspace/connections'
        thread_version = request.headers.get('Capstone-Thread-Version', '1')
        if request.url.path != "/health/ready" and request.url.hostname not in allowed_hosts:
            return JSONResponse({"error": "invalid_host"}, status_code=400)
        origin = request.headers.get("origin")
        if origin is not None and origin not in allowed_origins:
            return JSONResponse({"error": "invalid_origin"}, status_code=403)
        if request.method == "OPTIONS" and origin is not None:
            response = Response(status_code=204)
        elif request.url.path in {"/health/ready", "/api/v1/runtime-capacity", "/api/v1/thread-access", "/api/v1/workbench-preparation"} or (
            public_demo and request.url.path == "/api/v1/demo-credential"
        ):
            response = await call_next(request)
        else:
            expected = "Bearer " + operator_token
            supplied = request.headers.get("authorization", "")
            authorized = hmac.compare_digest(supplied, expected)
            demo_authorized = demo_token is not None and hmac.compare_digest(
                supplied, "Bearer " + demo_token,
            )
            if not authorized and not demo_authorized and not thread_open_access:
                response = JSONResponse({"error": "unauthorized"}, status_code=401)
            else:
                request.state.public_demo = demo_authorized
                scope_error = None
                try:
                    request.state.workspace_name = workspace_header(request.headers.get(WORKSPACE_HEADER))
                    # Check every Thread child route before version probing or
                    # parsing a body, including streaming and file endpoints.
                    parts = request.url.path.split('/')
                    if thread_resource and not demo_authorized and len(parts) >= 5 and parts[4] and thread_service is not None:
                        await run_in_threadpool(thread_service.require_workspace, parts[4], request.state.workspace_name)
                except ThreadNotFound:
                    scope_error = JSONResponse({'detail': 'thread not found'}, status_code=404)
                except ValueError:
                    scope_error = JSONResponse({'error': 'invalid_workspace'}, status_code=422)
                if scope_error is not None:
                    response = scope_error
                elif versioned_resource and not demo_authorized and thread_version not in {'1', '2'}:
                    response = JSONResponse({'error': 'unsupported_thread_version',
                                             'supported_versions': [1, 2]}, status_code=406)
                else:
                    upgrade = False
                    if thread_resource and not demo_authorized and thread_version == '1' and thread_service is not None:
                        parts = request.url.path.split('/')
                        if len(parts) >= 5 and parts[4] and not (request.method == 'POST' and parts[-1] == 'commands'):
                            try:
                                upgrade = (await asyncio.to_thread(thread_service.snapshot, parts[4])).minimum_protocol_version > 1
                            except ThreadNotFound:
                                pass
                    response = (JSONResponse({'error': 'protocol_upgrade_required', 'minimum_protocol_version': 2}, status_code=409)
                                if upgrade else await call_next(request))
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if thread_resource:
            response.headers.append('Vary', WORKSPACE_HEADER)
            selected_workspace = getattr(request.state, 'workspace_name', None)
            if selected_workspace is not None:
                response.headers[WORKSPACE_HEADER] = quote(selected_workspace, safe='')
        if versioned_resource:
            response.headers.append('Vary', 'Capstone-Thread-Version')
            if thread_version in {'1', '2'}:
                response.headers['Capstone-Thread-Version'] = thread_version
        if origin is not None:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers.append("Vary", "Origin")
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = (
                "Authorization, Content-Type, Idempotency-Key, Capstone-Thread-Version, Capstone-Workspace"
            )
            if thread_resource:
                response.headers['Access-Control-Expose-Headers'] = 'Capstone-Thread-Version, Capstone-Workspace'
        return response

    def get_session(session_id: str, request: Request) -> SessionRecord:
        record = ledger.get_session(session_id)
        if record is None:
            raise HTTPException(404, "session not found")
        if request.state.public_demo and (
            not record.public_demo
            or record.mode != "scripted-demo"
            or (record.application_id, record.case_id) not in public_cases
            or record.provider is not None
            or record.model is not None
        ):
            raise HTTPException(404, "session not found")
        return record

    @app.get("/health/ready")
    def health_ready():
        try:
            if ledger.ping():
                return {"status": "ready"}
        except Exception:
            pass
        raise HTTPException(503, "database unavailable")

    @app.get("/api/v1/runtime-capacity")
    def get_runtime_capacity():
        return current_capacity().to_document()

    @app.get("/api/v1/thread-access")
    def get_thread_access():
        # Keep cold-start waiting at the page entry, before any command UI is
        # available. A successful private wake proves both schedulers are up.
        health_ready()
        try:
            if wake_worker is not None and wake_worker() is False:
                raise HTTPException(503, "workbench is preparing")
        except (OSError, TimeoutError):
            raise HTTPException(503, "workbench is preparing") from None
        return {"schema": "capstone-thread-access/1",
                "mode": "open" if thread_open_access else "operator",
                "capacity": current_capacity().to_document()}

    @app.get("/api/v1/workbench-preparation")
    def prepare_workbench():
        def updates():
            def frame(component, status, *, complete=False):
                return json.dumps({'schema': 'capstone-workbench-preparation/1',
                    'component': component, 'status': status, 'complete': complete}) + '\n'
            yield frame('api', 'ready')
            yield frame('database', 'preparing')
            try:
                health_ready()
            except HTTPException:
                yield frame('database', 'failed')
                return
            yield frame('database', 'ready')
            if prepare_workers is not None:
                try:
                    for update in prepare_workers():
                        yield frame(update['component'], update['status'])
                        if update['status'] == 'failed':
                            return
                except (OSError, TimeoutError):
                    yield frame('workbench', 'failed')
                    return
            elif wake_worker is not None:
                yield frame('worker', 'preparing')
                try:
                    ready = wake_worker() is not False
                except (OSError, TimeoutError):
                    ready = False
                yield frame('worker', 'ready' if ready else 'failed')
                if not ready:
                    return
            yield frame('workbench', 'ready', complete=True)
        return StreamingResponse(updates(), media_type='application/x-ndjson',
                                 headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})

    @app.get("/api/v1/validation/m11")
    def get_validation_status(request: Request):
        if request.state.public_demo or validation_status is None:
            raise HTTPException(404, "validation status not found")
        try:
            return validation_status()
        except (OSError, ValueError):
            raise HTTPException(503, "validation workers are not ready") from None

    @app.get("/api/v1/catalog")
    def get_catalog():
        return catalog

    if thread_service is not None:
        def require_private_thread(request: Request) -> None:
            if request.state.public_demo:
                raise HTTPException(404, "thread not found")

        @app.get('/api/v1/workspace/connections')
        def workspace_connections(request: Request):
            require_private_thread(request)
            from .thread_input_catalog import public_gateway_identity
            publication = getattr(native_artifact_executor, 'capability', {}).get('data_gateway')
            identity = public_gateway_identity(publication)
            return {'schema': 'capstone-workspace-connections/1',
                    **({'data_gateway': identity} if identity is not None else {})}

        from .network_policy_http import register_network_policy_routes
        register_network_policy_routes(app, executor_provider=lambda: native_artifact_executor,
                                       authorize=require_private_thread)

        from .grid_source_http import register_grid_source_routes
        register_grid_source_routes(app, executor_provider=lambda: native_artifact_executor,
                                    authorize=require_private_thread)

        from .native_artifact_projection import register_native_artifact_routes
        register_native_artifact_routes(app, service=thread_service,
            executor_provider=lambda: native_artifact_executor, authorize=require_private_thread)
        from .thread_materials import register_material_routes
        material_objects = None if artifacts is None else artifacts.store
        thread_service.set_material_store(material_objects)
        register_material_routes(app, service=thread_service, objects=material_objects, authorize=require_private_thread)
        from .thread_resource_http import register_resource_routes
        register_resource_routes(app, service=thread_service, objects=material_objects, authorize=require_private_thread)
        from .thread_products import register_product_routes
        register_product_routes(app, service=thread_service, objects=material_objects,
            executor_provider=lambda: native_artifact_executor, authorize=require_private_thread)

        @app.get("/api/v1/threads")
        def list_threads(request: Request,
                         before: Annotated[str | None, Query(max_length=64)] = None,
                         limit: Annotated[int, Query(ge=1)] = 20,
                         archived: bool = False):
            require_private_thread(request)
            from .application_capacity import require_capacity
            require_capacity('history_page_items', limit, phase='thread_list')
            try:
                page = thread_service.list_threads(before=before, limit=limit, archived=archived,
                                                   workspace_name=request.state.workspace_name)
                if request.headers.get('Capstone-Thread-Version', '1') == '1' and any(
                        row.get('minimum_protocol_version', 1) > 1 for row in page['threads']):
                    return JSONResponse({'error': 'protocol_upgrade_required', 'minimum_protocol_version': 2}, status_code=409)
                return page
            except ThreadNotFound:
                raise HTTPException(404, "thread cursor not found") from None
            except ThreadProtocolError as error:
                raise HTTPException(422, str(error)) from None

        @app.delete('/api/v1/threads/{thread_id}', status_code=204)
        def delete_thread(thread_id: str, request: Request):
            require_private_thread(request)
            try:
                thread_service.delete_thread(thread_id)
            except ThreadNotFound:
                raise HTTPException(404, 'thread not found') from None
            except ThreadExecutionError:
                raise HTTPException(409, 'thread has active work') from None
            return Response(status_code=204)

        @app.post("/api/v1/threads/{thread_id}/archive")
        async def archive_thread(thread_id: str, request: Request):
            require_private_thread(request)
            try:
                body = await request.json()
                if not isinstance(body, dict) or set(body) != {"archived"} or type(body["archived"]) is not bool:
                    raise ThreadProtocolError("archive request requires archived boolean")
                return thread_service.set_archived(thread_id, body["archived"])
            except ThreadNotFound:
                raise HTTPException(404, "thread not found") from None
            except ThreadExecutionError:
                raise HTTPException(409, "thread has active work") from None
            except (ValueError, ThreadProtocolError):
                raise HTTPException(422, "invalid archive request") from None

        @app.get("/api/v1/threads/{thread_id}/metadata")
        def get_thread_metadata(thread_id: str, request: Request):
            require_private_thread(request)
            try:
                return {"thread_id": thread_id, "archived": thread_service.is_archived(thread_id)}
            except ThreadNotFound:
                raise HTTPException(404, "thread not found") from None

        @app.get("/api/v1/threads/{thread_id}/network-events")
        def get_thread_network_events(thread_id: str, request: Request,
                                     context_id: Annotated[str | None, Query(max_length=64)] = None,
                                     attempt_id: Annotated[str | None, Query(max_length=64)] = None):
            require_private_thread(request)
            try:
                if attempt_id is not None and context_id is None:
                    raise ThreadProtocolError("attempt target requires context")
                return (thread_service.read_network_events(thread_id) if context_id is None else
                        thread_service.read_network_events(thread_id, context_id=context_id, attempt_id=attempt_id))
            except ThreadNotFound:
                raise HTTPException(404, "thread not found") from None
            except ThreadProtocolError:
                raise HTTPException(503, "network context projection unavailable") from None

        @app.get("/api/v1/threads/{thread_id}/history")
        def get_thread_history(thread_id: str, request: Request,
                               before: Annotated[int | None, Query(ge=1)] = None,
                               limit: Annotated[int, Query(ge=1)] = 128):
            require_private_thread(request)
            from .application_capacity import require_capacity
            require_capacity('history_page_items', limit, phase='thread_history')
            try:
                return thread_service.read_history(thread_id, before=before, limit=limit)
            except ThreadNotFound:
                raise HTTPException(404, "thread not found") from None
            except ThreadProtocolError as error:
                raise HTTPException(422, str(error)) from None

        if thread_creator is not None:
            @app.get('/api/v1/thread-catalog')
            def session_entry_catalog(request: Request):
                require_private_thread(request)
                return thread_creator.entry_catalog()

            @app.post("/api/v1/threads", status_code=201)
            async def create_thread(request: Request, background_tasks: BackgroundTasks, response: Response):
                require_private_thread(request)
                try:
                    body = await request.json()
                    if not isinstance(body, dict):
                        raise ThreadProtocolError("thread creation must be an object")
                    unknown = set(body) - {"model_id", "session_type"}
                    if unknown:
                        raise ThreadProtocolError(
                            "thread creation has unknown field: " + ", ".join(sorted(unknown)),
                        )
                    model_id = body.get("model_id")
                    session_type = body.get('session_type')
                    if session_type is not None and session_type not in {'grid-analysis', 'enterprise-research', 'general-chat'}:
                        raise ThreadProtocolError('invalid session type')
                    if model_id is not None and (
                        not isinstance(model_id, str) or not model_id
                    ):
                        raise ThreadProtocolError("thread creation model_id is invalid")
                    started = time.perf_counter()
                    model_free = request.headers.get('Capstone-Thread-Version', '1') == '2' and model_id is None
                    workspace = ({} if request.state.workspace_name == DEFAULT_WORKSPACE
                                 else {'workspace_name': request.state.workspace_name})
                    if session_type is not None:
                        snapshot = await run_in_threadpool(thread_creator.create, model_id, model_free=model_free, session_type=session_type, **workspace)
                    else:
                        snapshot = (await run_in_threadpool(thread_creator.create, model_free=True, **workspace) if model_free
                                    else await run_in_threadpool(thread_creator.create, model_id, **workspace))
                    duration = record_thread_startup(snapshot.thread_id, 'thread_create', started)
                    response.headers['Server-Timing'] = f'thread_create;dur={duration:.3f}'
                    # Start the existing preparation as the response is sent. Task
                    # acquisition still prepares or reuses the same locked context.
                    if snapshot.active_model_context is not None:
                        background_tasks.add_task(request_model_preparation, snapshot.thread_id,
                                                  snapshot.active_model_context.implementation_family)
                    return snapshot.to_document()
                except ThreadProtocolError as error:
                    raise HTTPException(422, str(error)) from None
                except (LookupError, ValueError) as error:
                    raise HTTPException(422, str(error)) from None

        @app.get("/api/v1/threads/{thread_id}")
        def get_thread_snapshot(thread_id: str, request: Request):
            require_private_thread(request)
            try:
                snapshot = thread_service.snapshot(thread_id)
                if snapshot.minimum_protocol_version > int(request.headers.get('Capstone-Thread-Version', '1')):
                    return JSONResponse({'error': 'protocol_upgrade_required', 'minimum_protocol_version': 2}, status_code=409)
                return snapshot.to_document()
            except ThreadNotFound:
                raise HTTPException(404, "thread not found") from None

        @app.get("/api/v1/threads/{thread_id}/catalog")
        def get_thread_catalog(thread_id: str, request: Request):
            require_private_thread(request)
            try:
                if case_service is not None and thread_service.snapshot(thread_id).active_model_context is not None:
                    return case_service.catalog(thread_id)
                return thread_service.catalog(thread_id)
            except ThreadNotFound:
                raise HTTPException(404, "thread not found") from None

        @app.get("/api/v1/threads/{thread_id}/models")
        def get_thread_models(thread_id: str, request: Request):
            require_private_thread(request)
            try:
                return thread_service.read_models(thread_id)
            except ThreadNotFound:
                raise HTTPException(404, "thread not found") from None

        @app.get('/api/v1/threads/{thread_id}/input-catalog')
        def get_input_catalog(thread_id: str, request: Request):
            require_private_thread(request)
            try:
                from .thread_input_catalog import with_case_availability, public_input_catalog
                publication = getattr(native_artifact_executor, 'capability', {}).get('data_gateway')
                document = public_input_catalog(thread_service.input_catalog(thread_id), gateway_publication=publication)
                return with_case_availability(document, case_service.input_availability(thread_id)) if case_service is not None else document
            except ThreadNotFound:
                raise HTTPException(404, 'thread not found') from None
            except RuntimeError:
                raise HTTPException(503, 'input catalog unavailable') from None
        @app.get('/api/v1/threads/{thread_id}/products')
        def get_process_products(thread_id: str, request: Request,
                                 before: Annotated[int | None, Query(ge=1)] = None,
                                 limit: Annotated[int, Query(ge=1)] = 32):
            require_private_thread(request)
            from .application_capacity import require_capacity
            require_capacity('history_page_items', limit, phase='process_products')
            from .process_products import process_product_page
            try:
                return process_product_page(thread_service, thread_id, before=before, limit=limit)
            except ThreadNotFound:
                raise HTTPException(404, 'thread products not found') from None
            except ThreadProtocolError:
                raise HTTPException(422, 'product cursor is invalid') from None

        # Explicit task delivery uses the same authenticated Thread and ledger.
        @app.get('/api/v1/threads/{thread_id}/deliveries')
        def get_deliveries(thread_id: str, request: Request,
                           before: Annotated[int | None, Query(ge=1)] = None,
                           limit: Annotated[int, Query(ge=1)] = 32):
            require_private_thread(request)
            from .application_capacity import require_capacity
            require_capacity('product_page_items', limit, phase='deliveries')
            from .thread_deliveries import delivery_page
            try:
                return delivery_page(thread_service, thread_id, before=before, limit=limit)
            except ThreadNotFound:
                raise HTTPException(404, 'thread not found') from None

        @app.post('/api/v1/threads/{thread_id}/deliveries')
        async def post_delivery(thread_id: str, request: Request):
            require_private_thread(request)
            if artifacts is None:
                raise HTTPException(503, 'delivery storage unavailable')
            from .thread_deliveries import publish_delivery
            try:
                body = await request.body()
                if len(body) > 32768:
                    raise ValueError('delivery request exceeds bounds')
                document = json.loads(body)
                receipt = await run_in_threadpool(publish_delivery, thread_service,
                                                artifacts.store, thread_id, document,
                                                native_artifact_executor=native_artifact_executor)
                return JSONResponse(receipt.to_document(), status_code=201 if receipt.status == 'accepted' else 409)
            except KeyError:
                raise HTTPException(404, 'thread not found') from None
            except (ValueError, TypeError, UnicodeError):
                raise HTTPException(422, 'invalid or unavailable delivery request') from None
            except OSError:
                raise HTTPException(503, 'delivery content could not be stored') from None

        @app.get('/api/v1/threads/{thread_id}/deliveries/{artifact_id}/revisions/{revision}/content')
        def get_delivery_content(thread_id: str, artifact_id: str, revision: int, request: Request):
            require_private_thread(request)
            if artifacts is None:
                raise HTTPException(503, 'delivery storage unavailable')
            from .thread_deliveries import read_delivery_content, delivery_metadata
            from urllib.parse import quote
            try:
                metadata = delivery_metadata(thread_service, thread_id, artifact_id, revision)
                content = read_delivery_content(thread_service, artifacts.store, thread_id, artifact_id, revision)
            except KeyError:
                raise HTTPException(404, 'delivery revision not found') from None
            except ValueError:
                raise HTTPException(502, 'delivery content failed verification') from None
            except OSError:
                raise HTTPException(503, 'delivery content unavailable') from None
            disposition = ("attachment; filename*=UTF-8''" + quote(metadata['file_name'], safe='')
                           if metadata['format'] == 'native-file' else f'attachment; filename="{artifact_id}-r{revision}.md"')
            return Response(content, media_type=metadata['media_type'], headers={
                'Content-Disposition': disposition,
                'Content-Security-Policy': "default-src 'none'; sandbox",
            })

        @app.get("/api/v1/threads/{thread_id}/attempts/{attempt_id}/records")
        def get_attempt_records(thread_id: str, attempt_id: str, request: Request,
                                after: Annotated[int, Query(ge=0)] = 0,
                                limit: Annotated[int, Query(ge=1)] = 32):
            require_private_thread(request)
            from .application_capacity import require_capacity
            require_capacity('history_page_items', limit, phase='attempt_records')
            try:
                return thread_service.read_attempt_records(thread_id, attempt_id, after=after, limit=limit)
            except ThreadNotFound:
                raise HTTPException(404, "task records not found") from None
            except ThreadProtocolError:
                raise HTTPException(422, "task record cursor is invalid") from None

        @app.get("/api/v1/threads/{thread_id}/events")
        def get_thread_events(thread_id: str, request: Request,
                              after: Annotated[int, Query(ge=0)] = 0):
            require_private_thread(request)
            try:
                return thread_service.read_events(thread_id, after,
                    protocol_version=int(request.headers.get('Capstone-Thread-Version', '1'))).to_document()
            except ThreadProtocolUpgradeRequired:
                return JSONResponse({'error': 'protocol_upgrade_required', 'minimum_protocol_version': 2}, status_code=409)
            except ThreadNotFound:
                raise HTTPException(404, "thread not found") from None
            except ThreadResyncRequired as error:
                return JSONResponse(status_code=409, content={
                    "error": "resync_required",
                    "base_event_seq": error.snapshot.base_event_seq,
                    "snapshot": error.snapshot.to_document(),
                })

        @app.post("/api/v1/threads/{thread_id}/commands", status_code=202)
        async def post_thread_command(
            thread_id: str, request: Request, background_tasks: BackgroundTasks,
            idempotency_key: Annotated[str | None, Header(max_length=200)] = None,
        ):
            require_private_thread(request)
            try:
                command = await request.json()
                if not isinstance(command, dict):
                    raise ThreadProtocolError("command must be an object")
                if command.get("thread_id") != thread_id:
                    raise ThreadProtocolError("command.thread_id does not match route")
                version = request.headers.get('Capstone-Thread-Version', '1')
                if command.get('schema') == 'capstone-command/2' and version != '2':
                    raise ThreadProtocolError('command version does not match negotiated version')
                if idempotency_key is not None and command.get("idempotency_key") != idempotency_key:
                    raise HTTPException(400, "Idempotency-Key does not match command")
                kind = command.get("kind")
                if isinstance(kind, str) and kind in {
                    "start_case_execution", "retry_case_step", "resume_case_execution",
                } and thread_service.is_archived(thread_id):
                    return thread_service.record_rejected_command(command, rejection="thread_archived").to_document()
                service = (
                    case_service
                    if case_service is not None and isinstance(kind, str) and kind in {
                        "start_case_execution",
                        "retry_case_step",
                        "cancel_case_execution",
                        "resume_case_execution",
                    }
                    else thread_service
                )
                receipt = service.submit_command(command)
                if receipt.rejection == 'protocol_upgrade_required':
                    return JSONResponse({'error': 'protocol_upgrade_required', 'minimum_protocol_version': 2}, status_code=409)
                if receipt.status == 'accepted':
                    if kind in {'open_model', 'activate_model', 'switch_model', 'reopen_model_context'}:
                        await run_in_threadpool(request_model_preparation, thread_id)
                    if command.get('schema') != 'capstone-command/2' or kind in {'start_work', 'send_message'}:
                        background_tasks.add_task(request_worker, thread_id, force=True)
                return receipt.to_document()
            except ThreadNotFound:
                raise HTTPException(404, "thread not found") from None
            except ThreadProtocolError as error:
                raise HTTPException(422, str(error)) from None

        @app.get("/api/v1/threads/{thread_id}/events/stream")
        async def stream_thread_events(thread_id: str, request: Request,
                                       after: Annotated[int, Query(ge=0)] = 0,
                                       follow: Annotated[bool, Query()] = False):
            require_private_thread(request)
            try:
                initial_page = await asyncio.to_thread(thread_service.read_events, thread_id, after,
                    protocol_version=int(request.headers.get('Capstone-Thread-Version', '1')))
            except ThreadProtocolUpgradeRequired:
                return JSONResponse({'error': 'protocol_upgrade_required', 'minimum_protocol_version': 2}, status_code=409)
            except ThreadNotFound:
                raise HTTPException(404, "thread not found") from None
            except ThreadResyncRequired as error:
                return JSONResponse(status_code=409, content={
                    "error": "resync_required",
                    "base_event_seq": error.snapshot.base_event_seq,
                    "snapshot": error.snapshot.to_document(),
                })

            async def events():
                cursor = after
                page = initial_page
                first_page = True
                last_heartbeat = asyncio.get_running_loop().time()
                last_worker_keepalive = last_heartbeat
                idle_delay = 0.25
                while True:
                    if not first_page:
                        try:
                            page = await asyncio.to_thread(thread_service.read_events, thread_id, cursor,
                                protocol_version=int(request.headers.get('Capstone-Thread-Version', '1')))
                        except ThreadProtocolUpgradeRequired:
                            yield 'event: protocol_upgrade_required\ndata: {"error":"protocol_upgrade_required","minimum_protocol_version":2}\n\n'
                            return
                        except ThreadNotFound:
                            return
                        except ThreadResyncRequired as error:
                            payload = json.dumps({
                                "error": "resync_required",
                                "base_event_seq": error.snapshot.base_event_seq,
                                "snapshot": error.snapshot.to_document(),
                            }, ensure_ascii=False)
                            yield f"event: resync_required\ndata: {payload}\n\n"
                            return
                    first_page = False
                    if page.events:
                        idle_delay = 0.25
                        for event in page.events:
                            cursor = event.event_seq
                            payload = json.dumps(event.to_document(), ensure_ascii=False)
                            yield f"id: {event.event_seq}\nevent: {event.event_type}\ndata: {payload}\n\n"
                        if not follow:
                            return
                        continue
                    if not follow:
                        yield ": keepalive\n\n"
                        return
                    if await request.is_disconnected():
                        return
                    now = asyncio.get_running_loop().time()
                    if now - last_worker_keepalive >= 120:
                        # A connected workbench is active use. Keep workers
                        # available during reading; disconnect removes this
                        # traffic so the whole compute lane can sleep.
                        await asyncio.to_thread(request_worker, thread_id)
                        last_worker_keepalive = asyncio.get_running_loop().time()
                    if now - last_heartbeat >= 15:
                        yield ": keepalive\n\n"
                        last_heartbeat = now
                    await asyncio.sleep(idle_delay)
                    idle_delay = min(idle_delay * 2, 2.0)

            return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/api/v1/demo-credential")
    def get_demo_credential():
        if demo_token is None:
            raise HTTPException(404, "demo access is unavailable")
        return {"token": demo_token}

    @app.get("/api/v1/cases/{application_id}/{case_id}/diagram")
    def get_case_diagram(application_id: str, case_id: str):
        try:
            return diagrams.get(application_id, case_id)
        except KeyError:
            raise HTTPException(404, "case diagram is not registered") from None
        except Exception:
            raise HTTPException(503, "case diagram is unavailable") from None

    @app.post("/api/v1/sessions", status_code=201)
    def create_session(values: _CreateSession, request: Request,
                       idempotency_key: Annotated[str | None, Header(max_length=200)] = None):
        provider = values.provider
        model = values.model
        if request.state.public_demo:
            if values.mode != "scripted-demo" or (values.application_id, values.case_id) not in public_cases:
                raise HTTPException(403, "public demo only accepts registered cases")
            if provider is not None or model is not None:
                raise HTTPException(403, "public demo does not allow provider options")
        try:
            spec = registry.resolve(values.application_id)
        except ValueError:
            raise HTTPException(404, "application is not registered") from None
        try:
            WorkerSession(spec, mode=values.mode, case_id=values.case_id,
                          provider=provider, model=model)
        except ValueError:
            raise HTTPException(422, "application mode or case is invalid") from None
        try:
            record = ledger.create_session(values.application_id, values.mode, values.case_id,
                                           provider, model,
                                           idempotency_key=idempotency_key,
                                           public_demo=request.state.public_demo)
        except Conflict:
            raise HTTPException(409, "session key belongs to another request") from None
        if record.state == "pending":
            request_worker(record.session_id)
        return {"session_id": record.session_id, "run_id": None,
                "application_id": record.application_id, "state": "pending"}

    @app.post("/api/v1/sessions/{session_id}/turns", status_code=202)
    def submit_turn(session_id: str, values: _TurnInput, request: Request,
                    idempotency_key: Annotated[str | None, Header(max_length=200)] = None):
        get_session(session_id, request)
        try:
            command = ledger.accept_turn(session_id, values.instruction,
                                         idempotency_key or secrets.token_urlsafe(24))
        except KeyError:
            raise HTTPException(404, "session not found") from None
        except Conflict:
            raise HTTPException(409, "session cannot accept a turn") from None
        return {"session_id": session_id, "ordinal": command.ordinal, "state": "accepted"}

    @app.post("/api/v1/sessions/{session_id}/close", status_code=202)
    def close_session(session_id: str, request: Request,
                      idempotency_key: Annotated[str | None, Header(max_length=200)] = None):
        get_session(session_id, request)
        try:
            ledger.accept_close(session_id, idempotency_key or secrets.token_urlsafe(24))
        except KeyError:
            raise HTTPException(404, "session not found") from None
        except Conflict:
            raise HTTPException(409, "session cannot close") from None
        return {"session_id": session_id, "state": "closing"}

    @app.post("/api/v1/sessions/{session_id}/disconnect", status_code=200)
    def disconnect_session(session_id: str, request: Request,
                           idempotency_key: Annotated[str | None, Header(max_length=200)] = None):
        get_session(session_id, request)
        try:
            record = ledger.disconnect_session(
                session_id, idempotency_key or secrets.token_urlsafe(24),
            )
        except KeyError:
            raise HTTPException(404, "session not found") from None
        except Conflict:
            raise HTTPException(409, "session cannot disconnect") from None
        return _status(record)

    @app.get("/api/v1/sessions/{session_id}")
    def session_status(session_id: str, request: Request):
        record = get_session(session_id, request)
        if record.state == "pending":
            request_worker(session_id)
        return _status(record)

    @app.get("/api/v1/sessions/{session_id}/turns/{ordinal}")
    def get_turn(session_id: str, ordinal: int, request: Request):
        get_session(session_id, request)
        for event in ledger.events_after(session_id, 0):
            if event.kind == "answer_committed" and event.payload.get("ordinal") == ordinal:
                return event.payload
        raise HTTPException(404, "turn answer not found")

    @app.get("/api/v1/sessions/{session_id}/result")
    def get_result(session_id: str, request: Request):
        get_session(session_id, request)
        for event in ledger.events_after(session_id, 0):
            if event.kind == "completed":
                return event.payload["result"]
        raise HTTPException(409, "session has no final result")

    @app.get("/api/v1/sessions/{session_id}/network")
    def get_network(session_id: str, request: Request,
                    ordinal: Annotated[int, Query(ge=1, le=3)]):
        record = get_session(session_id, request)
        if record.completed_turns < ordinal:
            raise HTTPException(404, "network view not found")
        from capstone_agent.network_diagram import (
            normalize_network_diagram, normalize_network_layer,
        )

        diagrams: dict[str, dict[str, object]] = {}
        admitted: dict[int, tuple[str, ...]] = {}
        for event in ledger.events_after(session_id, 0):
            if event.kind == "answer_committed":
                step = event.payload.get("ordinal")
                refs = event.payload.get("result_refs")
                if type(step) is int and isinstance(refs, list):
                    admitted[step] = tuple(ref for ref in refs if isinstance(ref, str))
            if event.kind == "network_diagram":
                try:
                    diagram = normalize_network_diagram(event.payload.get("diagram"))
                except ValueError:
                    continue
                diagrams[diagram["ref"]] = diagram
            if event.kind == "network_layer" and event.payload.get("ordinal") == ordinal:
                raw = event.payload.get("layer")
                if not isinstance(raw, dict):
                    continue
                diagram_ref = raw.get("diagram_ref")
                if not isinstance(diagram_ref, str):
                    continue
                diagram = diagrams.get(diagram_ref)
                if diagram is None:
                    continue
                try:
                    layer = normalize_network_layer(
                        raw, diagram, ordinal, admitted_refs=admitted.get(ordinal, ()),
                    )
                except ValueError:
                    continue
                return {"schema": "capstone-network-view/2.0", "ordinal": ordinal,
                        "diagram": diagram, "layer": layer}
            if event.kind == "network_view" and event.payload.get("ordinal") == ordinal:
                return event.payload["view"]
        raise HTTPException(404, "network view not found")

    @app.get("/api/v1/sessions/{session_id}/network-story")
    def get_network_story(session_id: str, request: Request):
        record = get_session(session_id, request)
        if record.state != "completed":
            raise HTTPException(409, "network story is not ready")
        from capstone_agent.network_story import normalize_network_story

        story_event = None
        admitted: dict[int, tuple[str, ...]] = {}
        for event in ledger.events_after(session_id, 0):
            if event.kind == "answer_committed":
                ordinal = event.payload.get("ordinal")
                refs = event.payload.get("result_refs")
                if type(ordinal) is int and isinstance(refs, list):
                    admitted[ordinal] = tuple(ref for ref in refs if isinstance(ref, str))
            elif event.kind == "network_story":
                story_event = event.payload.get("story")
        if not isinstance(story_event, dict):
            raise HTTPException(404, "network story not found")
        try:
            return normalize_network_story(
                story_event, admitted_refs_by_ordinal=admitted,
            )
        except ValueError:
            raise HTTPException(502, "network story is invalid") from None

    @app.get("/api/v1/sessions/{session_id}/report")
    def get_report(session_id: str, request: Request):
        get_session(session_id, request)
        if artifacts is None:
            raise HTTPException(404, "report not found")
        try:
            report = artifacts.read_report(session_id)
        except (OSError, ValueError, KeyError):
            raise HTTPException(502, "report is unavailable") from None
        if report is None:
            raise HTTPException(404, "report not found")
        return Response(report, media_type="text/markdown; charset=utf-8")

    @app.get("/api/v1/sessions/{session_id}/evidence")
    def get_evidence(session_id: str, request: Request,
                     ref: Annotated[str, Query(min_length=1, max_length=2048)]):
        get_session(session_id, request)
        if artifacts is None:
            raise HTTPException(404, "evidence reference not found")
        try:
            value = artifacts.read_evidence(session_id, ref)
        except (OSError, ValueError, KeyError):
            raise HTTPException(502, "evidence is unavailable") from None
        if value is None:
            raise HTTPException(404, "evidence reference not found")
        return value

    @app.get("/api/v1/sessions/{session_id}/events")
    async def stream_events(session_id: str, request: Request,
                            after: Annotated[int, Query(ge=0)] = 0):
        get_session(session_id, request)

        async def events():
            cursor = after
            last_heartbeat = asyncio.get_running_loop().time()
            while True:
                rows = await asyncio.to_thread(ledger.events_after, session_id, cursor)
                for event in rows:
                    cursor = event.sequence
                    data = json.dumps({
                        "schema": "capstone-session-event/1.0",
                        "session_id": session_id, "sequence": cursor,
                        "event": event.kind, "payload": event.payload,
                    }, ensure_ascii=False)
                    yield f"id: {cursor}\nevent: {event.kind}\ndata: {data}\n\n"
                    if event.kind in {"completed", "failed"}:
                        return
                current = await asyncio.to_thread(ledger.get_session, session_id)
                if current is None or current.state in {"completed", "failed", "interrupted"}:
                    return
                now = asyncio.get_running_loop().time()
                if now - last_heartbeat >= 15:
                    yield ": keepalive\n\n"
                    last_heartbeat = now
                await asyncio.sleep(0.25)

        return StreamingResponse(events(), media_type="text/event-stream")

    return app
