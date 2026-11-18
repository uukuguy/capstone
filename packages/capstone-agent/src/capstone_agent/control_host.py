"""Application assembly for Control and the public Agent delegation port."""
import logging

from fastapi import HTTPException, Query, Request

from capstone_control.reconcile import reconcile
from capstone_control.service import ControlService, Conflict, InvalidTransition, public, fingerprint
from capstone_control.store import MemoryStore, PostgresStore

from .agent_delegation import AgentDelegations
from .agent_delegation_store import MemoryDelegations, PostgresDelegations


class ControlHost:
    def __init__(self, service, agent, *, verify_product, verify_answer=None):
        self.service, self.agent, self.verify_product = service, agent, verify_product
        self.verify_answer = verify_answer
        self.cursor = None

    def create_mission(self, workspace, request, *, claim=None):
        from .mission_origin import checked_origin, access
        origin = checked_origin(request.get('origin'))
        # Control and Agent own different ledgers. Creation is idempotent;
        # the origin lock serializes creation, and retry repairs partial writes.
        mission_id = 'goal_' + fingerprint([workspace, request.get('operation_id')])[:32]
        return access(self.agent.threads, workspace, origin, mission_id=mission_id, claim=claim,
            create=lambda: self.service.create_mission(workspace, request),
            active_missions=lambda: self.service.store.active_missions_for_thread(workspace, origin['thread_id']),
            read_state=lambda identity: self.service.read(workspace, identity)['state'])

    def read_mission(self, workspace, mission_id, *, claim=None):
        mission = self.service.read_mission(workspace, mission_id)
        if mission.get('origin') is not None:
            self.agent.threads.validate_mission_origin(workspace, mission['origin'], claim=claim)
        if claim is not None and mission.get('origin') is not None:
            from .mission_equipment import catalog
            try:
                resource_details = []
                mission['available_equipment'] = catalog(self.agent.threads, workspace, mission['origin'],
                                                         resource_details=resource_details)
                if resource_details:
                    mission['available_resource_details'] = resource_details
            except ValueError:
                mission['available_equipment'] = []
                mission['equipment_status'] = {'available': False,
                    'reason': 'Origin gateway requires its registered source adapter before delegation.'}
            excluded = set((claim.submission or {}).get('session_skills', {}).get('excluded', ()))
            mission['available_equipment'] = [ref for ref in mission['available_equipment']
                                              if ref['kind'] != 'skill' or ref['id'] not in excluded]
            from .agent_delegation import REGISTERED_AGENTS
            mission['registered_agents'] = sorted(REGISTERED_AGENTS)
        return mission

    def command_mission(self, workspace, command, *, actor='application:trusted', claim=None,
                        validate_task_equipment=False):
        from .mission_origin import access
        mission = self.read_mission(workspace, command['mission_id'], claim=claim)
        excluded_skills = () if claim is None else (claim.submission or {}).get('session_skills', {}).get('excluded', ())
        apply = lambda: self.service.command_mission(workspace, command, actor=actor,
                                                     validate_task_equipment=validate_task_equipment,
                                                     excluded_skills=excluded_skills)
        if mission.get('origin') is None:
            return apply()
        return access(self.agent.threads, workspace, mission['origin'], claim=claim, operation=apply,
                      required_mission_id=command['mission_id'])

    def command_goal(self, workspace, command, *, actor='application:trusted'):
        """Keep the legacy receipt while using Thread-before-Control lock order."""
        from .mission_origin import access
        goal = self.service.read(workspace, command['goal_id'])
        apply = lambda: self.service.command(workspace, command, actor=actor)
        origin = goal.get('origin') if goal.get('application_kind') == 'mission' else None
        if origin is None:
            return apply()
        return access(self.agent.threads, workspace, origin, operation=apply,
                      required_mission_id=command['goal_id'])

    def mission_operation(self, claim, name, arguments, *, operation_id):
        from .thread_service import ThreadExecutionError
        binding = (claim.submission or {}).get('_mission')
        if (not isinstance(binding, dict) or binding.get('schema') != 'capstone-native-mission/1'
                or not isinstance(arguments, dict)):
            raise ThreadExecutionError('Mission binding is unavailable')
        workspace, mission_id = claim.workspace_name, binding['mission_id']
        mission = self.read_mission(workspace, mission_id, claim=claim)
        if mission.get('origin') != binding.get('origin'):
            raise ThreadExecutionError('Mission origin binding changed')
        if name == 'agent_mission_read':
            if arguments:
                raise ValueError('Mission read takes no arguments')
            return mission
        if name == 'agent_mission_control':
            if set(arguments) != {'expected_revision', 'action'} or arguments['action'] not in {'pause', 'resume', 'cancel'}:
                raise ValueError('unsupported Mission control')
            return self.command_mission(workspace, {
                'schema': 'capstone-control-mission-command/1', 'operation_id': operation_id,
                'mission_id': mission_id, 'expected_revision': arguments['expected_revision'],
                'kind': arguments['action'], 'payload': {}},
                actor='agent:' + claim.attempt.attempt_id, claim=claim)
        kinds = {'agent_mission_update_plan': 'update_plan', 'agent_mission_prepare_task': 'prepare_task',
                 'agent_mission_ready': 'ready', 'agent_mission_conclude': 'conclude_plan',
                 'agent_mission_wait': 'wait'}
        if name not in kinds or 'expected_revision' not in arguments:
            raise ValueError('unsupported Mission operation')
        payload = {key: value for key, value in arguments.items() if key != 'expected_revision'}
        return self.command_mission(workspace, {
            'schema': 'capstone-control-mission-command/1', 'operation_id': operation_id,
            'mission_id': mission_id, 'expected_revision': arguments['expected_revision'],
            'kind': kinds[name], 'payload': payload}, actor='agent:' + claim.attempt.attempt_id, claim=claim,
            validate_task_equipment=True)

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
                if goal['state'] not in {'ready', 'running','waiting_review'}:
                    continue
                for task in goal['tasks']:
                    names = task.get('required_products', [])
                    if task['state'] != 'delivered':
                        continue
                    missing = set(task.get('required_reference_sources', ())) - task['delivery'].keys()
                    if missing:
                        continue
                    products = {p['file_name']: p for p in task['delivery']['products']}
                    if any(name not in products for name in names):
                        continue
                    checks = []
                    selected = [products[name] for name in names] if names else task['delivery']['products']
                    for product in selected:
                        self.verify_product(workspace, product)
                        checks.append({'name': product['file_name'] + ' · saved SHA-256 ' + product['sha256'], 'passed': True})
                    if not checks and self.verify_answer is not None:
                        self.verify_answer(workspace, task['delegation']['binding'],task['delivery']['answer_ref'])
                        checks.append({'name':'Saved answer reference '+task['delivery']['answer_ref'],'passed':True})
                    if not checks:
                        if goal.get('reason')!='delivery_verification_unavailable':
                            goal=self._command(goal,'defer_verification',{'task_id':task['task_id'],'reason':'delivery_verification_unavailable'})
                        continue
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
        return self.command_goal(goal['workspace'], {
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
    def verify_answer(workspace,binding,answer_ref):
        threads.require_workspace(binding['thread_id'],workspace)
        snapshot=threads.snapshot(binding['thread_id'])
        work=next(work for work in snapshot.works if work['work_id']==binding['work_id'])
        cursor=0
        for _ in range(128):
            page=threads.read_attempt_records(binding['thread_id'],work['latest_attempt_id'],after=cursor,limit=128)
            for event in page['events']:
                if (event['event_id']==answer_ref and event['event_type']=='attempt_completed'
                        and str(event['payload'].get('answer','')).strip()):
                    return
            if not page['has_more']:
                break
            if page['next_after']<=cursor:
                raise ValueError('saved answer cursor did not advance')
            cursor=page['next_after']
        raise ValueError('saved answer reference is not admitted for this Task')
    from .mission_equipment import admitted
    def admit_task(workspace, origin, task):
        from .agent_delegation import REGISTERED_AGENTS
        from .mission_equipment import resolve
        if task.get('agent_id') not in REGISTERED_AGENTS:
            return False
        try:
            resolve(threads, workspace, origin, task.get('equipment', []), task.get('restrictions', []))
        except (ValueError, KeyError):
            return False
        return True
    service = ControlService(store, mission_execution_adapter=True,
        admit_mission_task=admit_task,
        admit_mission_reference=lambda workspace, origin, ref: admitted(threads, workspace, origin, ref))
    host = ControlHost(service, AgentDelegations(threads, registry, wake=wake), verify_product=verify,verify_answer=verify_answer)
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
            if getattr(error, 'code', None) == 'mission_already_active':
                raise HTTPException(409, {'code': error.code, 'message': str(error),
                                          'mission_id': error.mission_id}) from None
            raise HTTPException(409, str(error)) from None
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

    @app.get('/api/v1/control/goals')
    def list_goals(request: Request, limit: int = Query(32, ge=1, le=64), after: str | None = None,
                   include_missions: bool = Query(False)):
        authorize(request)
        rows = host.service.store.list(request.state.workspace_name, limit + 1, after=after,
                                      include_missions=include_missions)
        return {'schema': 'capstone-control-goals/1', 'goals': [public(row) for row in rows[:limit]],
                'next_cursor': rows[limit - 1]['goal_id'] if len(rows) > limit else None}

    @app.get('/api/v1/control/missions')
    def list_missions(request: Request, limit: int = Query(32, ge=1, le=64), after: str | None = None):
        authorize(request)
        from capstone_control.mission import projection
        rows = host.service.store.list(request.state.workspace_name, limit + 1, after=after)
        return {'schema': 'capstone-control-missions/1',
                'missions': [projection(host.service, row) for row in rows[:limit]],
                'next_cursor': rows[limit - 1]['goal_id'] if len(rows) > limit else None}

    @app.post('/api/v1/control/missions', status_code=201)
    def create_mission(body: dict, request: Request):
        authorize(request)
        mission = run(host.create_mission, request.state.workspace_name, body)
        if wake:
            wake(mission['mission_id'])
        return mission

    @app.get('/api/v1/control/missions/{mission_id}')
    def read_mission(mission_id: str, request: Request):
        authorize(request)
        return run(host.read_mission, request.state.workspace_name, mission_id)

    @app.post('/api/v1/control/missions/{mission_id}/commands')
    def mission_command(mission_id: str, body: dict, request: Request):
        authorize(request)
        if body.get('mission_id') != mission_id:
            raise HTTPException(422, 'command Mission does not match route')
        receipt = run(host.command_mission, request.state.workspace_name, body,
                      actor=request.state.product_actor, validate_task_equipment=True)
        if wake:
            wake(mission_id)
        return receipt

    @app.get('/api/v1/control/missions/{mission_id}/events')
    def mission_events(mission_id: str, request: Request, after: int = Query(0, ge=0),
                       limit: int = Query(50, ge=1, le=100), through: int | None = Query(None, ge=0)):
        authorize(request)
        return run(host.service.read_events, request.state.workspace_name, mission_id,
                   after=after, limit=limit, through=through)

    @app.post('/api/v1/control/goals', status_code=201)
    def create_goal(body: dict, request: Request):
        authorize(request)
        goal = run(host.service.create, request.state.workspace_name, body)
        if wake:
            wake(goal['goal_id'])
        return goal

    @app.get('/api/v1/control/goals/{goal_id}')
    def read_goal(goal_id: str, request: Request, include_missions: bool = Query(False)):
        authorize(request)
        goal = run(host.service.read, request.state.workspace_name, goal_id)
        if goal.get('application_kind') == 'mission' and not include_missions:
            raise HTTPException(409, {'code': 'protocol_required', 'protocol': 'capstone-control-mission/1',
                                     'message': 'This Mission requires an updated client.'})
        return goal

    @app.post('/api/v1/control/goals/{goal_id}/commands')
    def command(goal_id: str, body: dict, request: Request):
        authorize(request)
        if body.get('goal_id') != goal_id:
            raise HTTPException(422, 'command Goal does not match route')
        receipt = run(host.command_goal, request.state.workspace_name, body,
                      actor=request.state.product_actor)
        if wake:
            wake(goal_id)
        return receipt

    @app.get('/api/v1/control/goals/{goal_id}/events')
    def read_events(goal_id: str, request: Request, after: int = Query(0, ge=0),
                    limit: int = Query(50, ge=1, le=100), through: int | None = Query(None, ge=0)):
        authorize(request)
        return run(host.service.read_events, request.state.workspace_name, goal_id,
                   after=after, limit=limit, through=through)

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
