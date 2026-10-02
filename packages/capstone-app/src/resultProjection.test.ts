import { describe, expect, it } from 'vitest'
import { parseResultProjection, ThreadProtocolError } from './threadProtocol'

const projection = {
  schema: 'capstone-result-projection/1.0',
  result_id: 'result_projection_1',
  result_ref: `result:sha256:${'a'.repeat(64)}`,
  evidence_refs: [`evidence:sha256:${'b'.repeat(64)}`],
  thread_id: 'thread_1', run_id: 'run_1', turn_id: 'turn_1', attempt_id: 'attempt_1',
  model_context_id: 'context_1', model_id: 'ieee39', model_revision: `revision:sha256:${'c'.repeat(64)}`,
  source: { capability_id: 'analysis.powerflow.ac.run', domain_pack_id: 'pandapower-static-analysis', implementation_family: 'pandapower' },
  status: 'completed',
  summary: [{ metric_id: 'total_active_loss', label: '有功损耗', value: 43.64, unit: 'MW' }],
  tables: [{ table_id: 'line_loading', title: '线路负载率', columns: [{ column_id: 'line', label: '线路' }], rows: [{ row_id: 'line_11', cells: { line: '11' }, element_ref: { element_kind: 'line', element_id: 'line_11' } }] }],
  element_refs: [{ element_kind: 'line', element_id: 'line_11' }],
  overlay: null,
}

describe('parseResultProjection', () => {
  it('parses the bounded public shape', () => {
    const parsed = parseResultProjection(projection)
    expect(parsed.resultRef).toBe(projection.result_ref)
    expect(parsed.tables[0].rows[0].elementRef?.elementId).toBe('line_11')
  })

  it('rejects malformed public values with a protocol error', () => {
    expect(() => parseResultProjection({ ...projection, summary: [{ ...projection.summary[0], value: Number.NaN }] })).toThrow(ThreadProtocolError)
  })
})
