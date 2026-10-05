import { sampleDiagramView } from './networkFixture'
import type { ThreadFixtureDocument } from './threadProjectionStore'

export const historyContexts = {
  initial: { id: 'ctx_ieee_old', model_id: 'ieee39', model_revision: `revision:sha256:${'c'.repeat(64)}`, implementation_family: 'pandapower', selection_revision: 'sel_0' },
  historical: { id: 'ctx_regional', model_id: 'regional-six-bus', model_revision: `revision:sha256:${'d'.repeat(64)}`, implementation_family: 'pypsa', selection_revision: 'sel_1' },
  active: { id: 'ctx_ieee_new', model_id: 'ieee39', model_revision: `revision:sha256:${'c'.repeat(64)}`, implementation_family: 'pandapower', selection_revision: 'sel_2' },
}

export function historyFixture(includeHistoricalNetwork = true): ThreadFixtureDocument {
  const events: Record<string, unknown>[] = []
  const append = (event_type: string, context: typeof historyContexts.initial, payload: Record<string, unknown>) => {
    const event_seq = events.length + 1
    events.push({
      event_id: `evt_${event_seq}`, event_seq, event_type, event_version: 1,
      thread_id: 'thr_history', run_id: 'run_history', model_context_id: context.id,
      turn_id: 'turn_result', attempt_id: 'attempt_result', selection_revision: context.selection_revision,
      occurred_at: '2026-10-05T00:00:00Z', visibility: 'public', payload,
    })
  }
  const network = (context: typeof historyContexts.initial) => {
    append('network_diagram', context, { diagram: {
      ...sampleDiagramView.diagram, model: { id: context.model_id, revision: context.model_revision, source: context.implementation_family === 'pypsa' ? 'pypsamodelctl' : 'gridctl' },
    } })
    append('network_layer', context, { ordinal: 1, layer: { ...sampleDiagramView.layer, model_revision: context.model_revision, focus_ids: [] } })
  }
  network(historyContexts.initial)
  append('model_context_activated', historyContexts.historical, {
    model_context: historyContexts.historical, active_grid_page_id: 'page_regional-six-bus',
    previous_context: historyContexts.initial, previous_grid_page_id: 'page_ieee39',
  })
  if (includeHistoricalNetwork) network(historyContexts.historical)
  append('model_context_activated', historyContexts.active, {
    model_context: historyContexts.active, active_grid_page_id: 'page_ieee39',
    previous_context: historyContexts.historical, previous_grid_page_id: 'page_regional-six-bus',
  })
  network(historyContexts.active)
  return {
    snapshot: {
      schema: 'capstone-thread-snapshot/1', thread_id: 'thr_history', run: { run_id: 'run_history', state: 'open' },
      active_model_context: historyContexts.active, active_grid_page_id: 'page_ieee39',
      current_attempt: null, base_event_seq: 0, last_event_seq: events.length,
    },
    events: { schema: 'capstone-thread-events/1', thread_id: 'thr_history', after_event_seq: 0, next_event_seq: events.length, has_more: false, events },
    catalog: { schema: 'capstone-thread-catalog/1', models: [], profiles: [] },
  }
}
