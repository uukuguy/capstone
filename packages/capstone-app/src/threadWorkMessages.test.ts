import { expect, it } from 'vitest'
import { projectWorkConversation } from './threadWorkMessages'
import type { EventEnvelope } from './threadProtocol'
import type { WorkRecord } from './threadWorkProtocol'

const work = (workId: string, attemptId: string): WorkRecord => ({ workId, goal: workId, goalRevision: 1, revision: 1,
  status: 'running', blockedReason: null, messages: [workId], latestAttemptId: attemptId, startAvailable: false, startUnavailableReason: 'attempt_in_progress' })
const delta = (attemptId: string): EventEnvelope => ({ eventId: 'evt_delta', eventSeq: 1200, eventType: 'assistant_text_delta', eventVersion: 1,
  threadId: 'thr_work', runId: 'run_work', attemptId, turnId: 'turn_one', visibility: 'public', occurredAt: '2026-10-17T00:00:00Z', payload: { text: 'A的运行内容' } })

it('uses every Work latest Attempt when its boundary events are outside the restored window', () => {
  const a = work('work_a', 'attempt_a'); const b = work('work_b', 'attempt_b')
  const projected = projectWorkConversation([delta('attempt_a')], b, [a, b])
  expect(projected.messages.some(message => message.role === 'assistant')).toBe(false)
  expect(projected.events).toEqual([])
  expect(projectWorkConversation([delta('attempt_a')], a, [a, b]).messages.some(message => message.role === 'assistant')).toBe(true)
})

it.each(['assistant_text_delta', 'attempt_completed', 'tool_completed'])('isolates unknown historical %s until its Attempt ownership is confirmed', eventType => {
  const projected = projectWorkConversation([{ ...delta('attempt_old'), eventType }], work('work_b', 'attempt_b'))
  expect(projected.events).toEqual([])
  expect(projected.hasUnattributedHistory).toBe(true)
  const confirmed = { ...delta('attempt_old'), eventId: 'evt_start', eventSeq: 100, eventType: 'command_accepted', payload: { kind: 'send_auto', payload: { text: '旧专业指令' } } }
  expect(projectWorkConversation([confirmed, delta('attempt_old')]).hasUnattributedHistory).toBe(false)
})
