"""Application assembly for Control and the public Agent delegation port."""
import logging

from fastapi import HTTPException, Query, Request

from capstone_control.reconcile import reconcile
from capstone_control.service import ControlService, Conflict, InvalidTransition, public, fingerprint
from capstone_control.store import MemoryStore, PostgresStore

from .agent_delegation import AgentDelegations
from .agent_delegation_store import MemoryDelegations, PostgresDelegations


class ControlHost:
    def __init__(self, service, agent, *, verify_product):
        self.service, self.agent, self.verify_product = service, agent, verify_product
        self.cursor = None

    def tick(self, limit=32):
        """One bounded maintenance pass; no model calls or browser dependency."""
        goals = self.service.store.list(limit=limit, after=self.cursor, active_only=True)
        if not goals:
            self.cursor = None
            return
        self.cursor = goals[-1]['goal_id']
        for original in goals:
            workspace, goal_id = original['workspace'], original['goal_id']
            try:
                reconcile(self.service, self.agent, workspace=workspace, goal_id=goal_id)
                goal = self.service.read(workspace, goal_id)
                if goal['state'] not in {'ready', 'running'}:
                    continue
                for task in goal['tasks']:
                    names = task.get('required_products', [])
                    if task['state'] != 'delivered' or not names:
                        continue
                    products = {p['file_name']: p for p in task['delivery']['products']}
                    if any(name not in products for name in names):
                        continue
                    checks = []
                    for name in names:
                        product = products[name]
                        self.verify_product(workspace, product)
                        checks.append({'name': name + ' · saved SHA-256 ' + product['sha256'], 'passed': True})
                    goal = self._command(goal, 'verify_task', {
                        'task_id': task['task_id'], 'delivery_revision': task['delivery']['revision'], 'checks': checks})
                if goal['state'] not in {'ready', 'running'}:
                    continue
                active = {'dispatching', 'running', 'waiting', 'resume_requested', 'revoke_requested'}
                verified = {t['task_id'] for t in goal['tasks'] if t['state'] == 'verified'}
                if (not any(t['state'] in active for t in goal['tasks']) and
                        any(t['state'] == 'pending' and set(t['depends_on']) <= verified for t in goal['tasks'])):
                    self._command(goal, 'delegate_next', {})
            except Exception:
                # A failed check never releases a dependency. Retain the exact
                # intent and products; avoid logging credential-bearing errors.
                logging.getLogger(__name__).warning('Control maintenance incomplete; durable state retained')

    def _command(self, goal, kind, payload):
        operation = 'host_' + fingerprint([goal['goal_id'], goal['revision'], kind, payload])[:32]
        return self.service.command(goal['workspace'], {
            'schema': 'capstone-control-command/1', 'operation_id': operation,
            'goal_id': goal['goal_id'], 'expected_revision': goal['revision'],
            'kind': kind, 'payload': payload}, actor='application:saved-products')['goal']


def configure_control(threads, *, wake=None):
    existing = getattr(threads, 'control_host', None)
    if existing is not None:
        return existing
    dsn = getattr(threads, 'dsn', None)
    store = PostgresStore(dsn) if dsn else MemoryStore()
    registry = PostgresDelegations(dsn) if dsn else MemoryDelegations()
    if dsn:
        store.initialize()
        registry.initialize()
    def verify(workspace, product):
        from .native_artifact_projection import read_native_artifact
        threads.require_workspace(product['thread_id'], workspace)
        read_native_artifact(threads, getattr(threads, '_native_executor', None),
            product['thread_id'], product['attempt_id'], product['artifact_id'], expected_descriptor=product)
    host = ControlHost(ControlService(store), AgentDelegations(threads, registry, wake=wake), verify_product=verify)
    threads.control_host = host
    return host


def register_control_routes(app, *, threads, authorize, wake=None):
    host = configure_control(threads, wake=wake)

    def run(operation, *args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except KeyError:
            raise HTTPException(404, 'control resource not found') from None
        except (Conflict, InvalidTransition) as error:
            raise HTTPException(409, str(error)) from None
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

    @app.get('/api/v1/control/goals')
    def list_goals(request: Request, limit: int = Query(32, ge=1, le=64), after: str | None = None):
        authorize(request)
        rows = host.service.store.list(request.state.workspace_name, limit + 1, after=after)
        return {'schema': 'capstone-control-goals/1', 'goals': [public(row) for row in rows[:limit]],
                'next_cursor': rows[limit - 1]['goal_id'] if len(rows) > limit else None}

    @app.post('/api/v1/control/goals', status_code=201)
    def create_goal(body: dict, request: Request):
        authorize(request)
        goal = run(host.service.create, request.state.workspace_name, body)
        if wake:
            wake(goal['goal_id'])
        return goal

    @app.get('/api/v1/control/goals/{goal_id}')
    def read_goal(goal_id: str, request: Request):
        authorize(request)
        return run(host.service.read, request.state.workspace_name, goal_id)

    @app.post('/api/v1/control/goals/{goal_id}/commands')
    def command(goal_id: str, body: dict, request: Request):
        authorize(request)
        if body.get('goal_id') != goal_id:
            raise HTTPException(422, 'command Goal does not match route')
        receipt = run(host.service.command, request.state.workspace_name, body,
                      actor=request.state.product_actor)
        if wake:
            wake(goal_id)
        return receipt

    @app.post('/api/v1/agent/delegations')
    def delegate(body: dict, request: Request):
        authorize(request)
        return run(host.agent.delegate, request.state.workspace_name, body)

    @app.post('/api/v1/agent/delegations/observe')
    def observe(body: dict, request: Request):
        authorize(request)
        return run(host.agent.observe, request.state.workspace_name, body)

    @app.post('/api/v1/agent/delegations/control')
    def control(body: dict, request: Request):
        authorize(request)
        if set(body) != {'delegation', 'kind', 'operation_id'}:
            raise HTTPException(422, 'invalid Agent control fields')
        return run(host.agent.control, request.state.workspace_name,
                   body['delegation'], body['kind'], body['operation_id'])
    return host
