import { describe, expect, it } from 'vitest'
import { parseCaseExecutionSnapshot, parseThreadSnapshot, ThreadProtocolError } from './threadProtocol'

function caseState(attemptId: string) {
  return {
    display_name: 'IEEE-39 潮流与线路筛查', status: 'blocked', completed_steps: 1, total_steps: 2, current_step: 2,
    steps: [
      { ordinal: 1, title: '打开 IEEE-39 模型', status: 'completed', duration_ms: 1200, details: { turn_id: 'turn_a', attempt_id: attemptId } },
      { ordinal: 2, title: '执行交流潮流', status: 'failed', duration_ms: null, details: { turn_id: 'turn_b', attempt_id: attemptId } },
    ],
    actions: [{ action_id: 'retry_case_step', label: '重试此步骤', enabled: true }, { action_id: 'cancel_case', label: '停止案例', enabled: true }],
    disabled_reasons: ['运行被中断'],
  }
}

describe('shared Case interaction projection', () => {
  it('parses bounded state and keeps labels stable across internal IDs', () => {
    const first = parseCaseExecutionSnapshot(caseState('attempt_a'))
    const second = parseCaseExecutionSnapshot(caseState('attempt_b'))
    expect(first.displayName).toBe(second.displayName)
    expect(first.steps[0].title).toBe(second.steps[0].title)
    expect(first.steps[0].details.attempt_id).not.toBe(second.steps[0].details.attempt_id)
  })

  it('rejects malformed Case state in a Thread snapshot', () => {
    expect(() => parseThreadSnapshot({
      schema: 'capstone-thread-snapshot/1', thread_id: 'thr_demo', run: { run_id: 'run_demo', state: 'open' },
      active_model_context: { id: 'ctx_demo', model_id: 'ieee39', model_revision: '7', implementation_family: 'pandapower', selection_revision: 'sel_1' },
      active_grid_page_id: 'page_demo', current_attempt: null, last_event_seq: 0, base_event_seq: 0,
      application_state: { case_execution: { ...caseState('attempt_a'), extra: true } },
    })).toThrowError(ThreadProtocolError)
  })
})
