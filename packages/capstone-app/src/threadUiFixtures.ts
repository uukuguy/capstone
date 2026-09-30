import type { ThreadFixtureDocument } from './threadProjectionStore'

export type ThreadUiFixtureId =
  | 'idle-ieee39'
  | 'historical-live-attempt'
  | 'resync-required'
  | 'interrupted-attempt'

export type ThreadUiFixture = ThreadFixtureDocument & {
  fixture_id: ThreadUiFixtureId
  local_view: { viewed_grid_page_id: string; draft: string; replay: null | Record<string, unknown>; element_reference?: { model_id: string; model_revision: string; element_kind: string; element_id: string } }
  assertions: { transport_state?: string; enabled_commands: string[] }
}

const context = {
  id: 'ctx_ieee39_7', model_id: 'ieee39', model_revision: '7',
  implementation_family: 'pandapower', selection_revision: 'sel_2',
}

const baseSnapshot = {
  schema: 'capstone-thread-snapshot/1', thread_id: 'thr_demo_39',
  run: { run_id: 'run_001', state: 'open' }, active_model_context: context,
  active_grid_page_id: 'page_ieee39', current_attempt: null,
  last_event_seq: 0, base_event_seq: 0,
}

const historicalEvents = [
  {
    event_id: 'evt_181', event_seq: 181, event_type: 'grid_page_registered', event_version: 1,
    thread_id: 'thr_demo_39', run_id: 'run_001', occurred_at: '2026-09-30T00:00:01Z',
    visibility: 'public', payload: { grid_page_id: 'page_scigrid_2' },
  },
  {
    event_id: 'evt_182', event_seq: 182, event_type: 'grid_page_viewed', event_version: 1,
    thread_id: 'thr_demo_39', run_id: 'run_001', occurred_at: '2026-09-30T00:00:02Z',
    visibility: 'public', payload: { grid_page_id: 'page_scigrid_2', view_only: true },
  },
  {
    event_id: 'evt_183', event_seq: 183, event_type: 'attempt_progress', event_version: 1,
    thread_id: 'thr_demo_39', run_id: 'run_001', turn_id: 'turn_004', attempt_id: 'attempt_004a',
    model_context_id: 'ctx_ieee39_7', selection_revision: 'sel_2', occurred_at: '2026-09-30T00:00:03Z',
    visibility: 'public', payload: { phase: 'running' },
  },
]

function fixture(value: Omit<ThreadUiFixture, 'snapshot' | 'events'> & {
  snapshot: Record<string, unknown>; events: Record<string, unknown>
}): ThreadUiFixture {
  return value
}

const fixtures: Record<ThreadUiFixtureId, ThreadUiFixture> = {
  'idle-ieee39': fixture({
    fixture_id: 'idle-ieee39', snapshot: baseSnapshot,
    events: { schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39', after_event_seq: 0, next_event_seq: 0, has_more: false, events: [] },
    local_view: { viewed_grid_page_id: 'page_ieee39', replay: null, draft: '' },
    assertions: { transport_state: 'live', enabled_commands: ['send_auto', 'send_professional', 'model_switch', 'replace_selection', 'launch_case'] },
  }),
  'historical-live-attempt': fixture({
    fixture_id: 'historical-live-attempt',
    snapshot: { ...baseSnapshot, current_attempt: { turn_id: 'turn_004', attempt_id: 'attempt_004a', phase: 'running', target_model_context_id: 'ctx_ieee39_7' }, last_event_seq: 180, base_event_seq: 180 },
    events: { schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39', after_event_seq: 180, next_event_seq: 183, has_more: false, events: historicalEvents },
    local_view: { viewed_grid_page_id: 'page_scigrid_2', replay: null, draft: '停止当前计算' },
    assertions: { transport_state: 'live', enabled_commands: ['cancel_live_attempt', 'send_control', 'return_live', 'open_replay'] },
  }),
  'resync-required': fixture({
    fixture_id: 'resync-required', snapshot: { ...baseSnapshot, last_event_seq: 200, base_event_seq: 200 },
    events: { schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39', after_event_seq: 200, next_event_seq: 200, has_more: false, events: [] },
    local_view: { viewed_grid_page_id: 'page_ieee39', replay: null, draft: '继续查看潮流结果' },
    assertions: { transport_state: 'resync_required', enabled_commands: ['reconnect', 'resync', 'help', 'exit'] },
  }),
  'interrupted-attempt': fixture({
    fixture_id: 'interrupted-attempt',
    snapshot: { ...baseSnapshot, current_attempt: { turn_id: 'turn_008', attempt_id: 'attempt_008a', phase: 'interrupted', target_model_context_id: 'ctx_ieee39_7' }, last_event_seq: 50, base_event_seq: 50 },
    events: { schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39', after_event_seq: 50, next_event_seq: 50, has_more: false, events: [] },
    local_view: { viewed_grid_page_id: 'page_ieee39', replay: null, draft: '',
      element_reference: { model_id: 'ieee39', model_revision: '6', element_kind: 'branch', element_id: 'line_12' } },
    assertions: { transport_state: 'live', enabled_commands: ['retry_new_attempt', 'open_replay', 'return_live'] },
  }),
}

export function listThreadFixtureIds(): ThreadUiFixtureId[] {
  return Object.keys(fixtures) as ThreadUiFixtureId[]
}

export function threadUiFixture(value: string): ThreadUiFixture {
  if (!Object.prototype.hasOwnProperty.call(fixtures, value)) throw new Error(`unknown thread fixture: ${value}`)
  return fixtures[value as ThreadUiFixtureId]
}
