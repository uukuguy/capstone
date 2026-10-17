import { describe, expect, it } from 'vitest'
import { parseWorkSnapshot, buildWorkCommand, buildStartWorkCommand } from './threadWorkProtocol'

export function workSnapshot() {
  return { schema: 'capstone-thread-snapshot/2', thread_id: 'thr_work',
    run: { run_id: 'run_work', state: 'open' }, active_model_context: null,
    active_grid_page_id: null, current_attempt: null, last_event_seq: 0, base_event_seq: 0,
    minimum_protocol_version: 2, selected_model_context_id: null, task_context: null, works: [] }
}

describe('Work protocol', () => {
  it('starts an existing Work with object CAS and no fabricated instruction payload', () => {
    const command = buildStartWorkCommand('thr_work', 'run_work', 'cmd_start', 'idem_start', 'work_one', 3)
    expect(command.kind).toBe('start_work')
    expect(command.payload).toEqual({})
    expect(command.target.expected_revision).toBe(3)
    expect(command).not.toHaveProperty('expected_event_seq')
    expect(() => buildStartWorkCommand('thr_work', 'run_work', 'cmd_start', 'idem_start', 'new', 0)).toThrow()
  })
  it('reads a model-free Thread without inventing a model', () => {
    const snapshot = parseWorkSnapshot(workSnapshot())
    expect(snapshot.threadId).toBe('thr_work')
    expect(snapshot.works).toEqual([])
    expect(snapshot.selectedModelContextId).toBeNull()
  })
  it('rejects an unsupported schema and inconsistent event cursor', () => {
    expect(() => parseWorkSnapshot({ ...workSnapshot(), schema: 'capstone-thread-snapshot/3' })).toThrow()
    expect(() => parseWorkSnapshot({ ...workSnapshot(), base_event_seq: 2 })).toThrow()
  })
  it('uses object revision rather than event sequence for a new Work', () => {
    const command = buildWorkCommand('thr_work', 'run_work', 'cmd_save', 'key_save', 'new', 0, '整理所提供的资料')
    expect(command.target).toEqual({ kind: 'work', id: 'new', expected_revision: 0 })
    expect(command).not.toHaveProperty('expected_event_seq')
    expect(command.kind).toBe('work_message')
  })
  it('limits the encoded command, including multibyte task text', () => {
    expect(() => buildWorkCommand('thr_work', 'run_work', 'cmd_save', 'key_save', 'new', 0, '中'.repeat(22000))).toThrow()
  })
})
