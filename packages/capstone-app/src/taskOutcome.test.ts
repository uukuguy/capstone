import { expect, it } from 'vitest'
import { parseTaskOutcome } from './taskOutcome'

const value = { schema: 'capstone-task-outcome/1', status: 'partial', work: [
  { id: 'saved', status: 'confirmed', summary: '已保存场景。', result_refs: [], evidence_refs: [] },
  { id: 'scope', status: 'blocked', summary: '范围未确认。', result_refs: [], evidence_refs: [] },
], diagnostics: [], coverage: { requested_scope: 'unconfirmed', completed_scenario_count: 1,
  scenario_context_refs: ['context:sha256:' + 'a'.repeat(64)], full_ranking_allowed: false } }

it('restores bounded scope without allowing a full ranking claim', () => {
  expect(parseTaskOutcome(value)?.coverage?.completed_scenario_count).toBe(1)
  expect(parseTaskOutcome({ ...value, coverage: { ...value.coverage, full_ranking_allowed: true } })).toBeUndefined()
  expect(parseTaskOutcome({ ...value, status: 'complete' })).toBeUndefined()
  expect(parseTaskOutcome({ ...value, raw_error: 'SECRET' })).toBeUndefined()
})
