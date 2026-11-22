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

it('reconstructs native conversation turns from the ledger after pending messages are consumed', () => {
  const selected = {...work('work_a', 'attempt_b'), conversationMode: true, messages: []}
  const events: EventEnvelope[] = []
  for (const [index, text] of ['你好', '继续说明'].entries()) {
    const attemptId = index ? 'attempt_b' : 'attempt_a'
    const base = {...delta(attemptId), turnId: `turn_${index}`, payload: {work_id: 'work_a'}}
    events.push({...base, eventId: `evt_user_${index}`, eventSeq: index * 3 + 1, eventType: 'command_accepted', payload: {work_id: 'work_a', kind: 'send_auto', payload: {text}}})
    events.push({...base, eventId: `evt_delta_${index}`, eventSeq: index * 3 + 2, payload: {text: '临时流式'}})
    events.push({...base, eventId: `evt_done_${index}`, eventSeq: index * 3 + 3, eventType: 'attempt_completed', payload: {work_id: 'work_a', answer: `完整答复${index}`}})
  }
  const projected = projectWorkConversation(events, selected, [selected])
  expect(projected.messages.map(message => [message.role, message.content])).toEqual([
    ['user', '你好'], ['assistant', [{type: 'text', text: '完整答复0'}]],
    ['user', '继续说明'], ['assistant', [{type: 'text', text: '完整答复1'}]],
  ])
})

it('shows the actual Goal step as an Instruction with its own Attempt', () => {
  const selected = work('work_a', 'attempt_a')
  const admission: EventEnvelope = {...delta('attempt_a'), eventId: 'evt_goal_step', eventSeq: 1,
    eventType: 'command_accepted', payload: {kind: 'send_auto', work_id: 'work_a',
      payload: {text: '检查输入'}, work: {goal_plan: {plan: {steps: [
        {instruction: '检查输入'}, {instruction: '编写报告'},
      ]}}}}}
  const rows = projectWorkConversation([admission], selected, [selected]).messages
  expect(rows.filter(row => row.role === 'user').map(row => row.content)).toEqual(['work_a', '检查输入'])
  expect(rows.find(row => row.content === '检查输入')?.metadata?.custom).toMatchObject({
    eventId: 'evt_goal_step', attemptId: 'attempt_a', goalStep: '1/2',
  })
})

it('shows persisted Goal decisions once and gives the completed Goal its own reply', () => {
  const selected = work('work_a', 'attempt_a')
  const decision: EventEnvelope = {...delta('attempt_a'), eventId: 'evt_goal_decision', eventSeq: 2,
    eventType: 'command.applied', payload: {work_id: 'work_a', work: {
      work_id: 'work_a', goal_mode: {state: 'ready', generation: 1, last_settled_attempt_id: 'attempt_a'},
      goal_plan: {last_decision: '已核对输入。下一步生成报告。'},
    }}}
  const close: EventEnvelope = {...decision, eventId: 'evt_goal_close', eventSeq: 4, payload: {
    work_id: 'work_a', work: {work_id: 'work_a',
      goal_mode: {state: 'completed', generation: 1, last_settled_attempt_id: 'attempt_b'},
      goal_plan: {closure_summary: '已完成报告及复核。'},
    },
  }}
  const rows = projectWorkConversation([decision, {...decision,eventId:'evt_repeat',eventSeq:3}, close], selected, [selected]).messages
  expect(rows.filter(row=>row.metadata?.custom?.systemNotice).map(row=>row.content)).toEqual([
    'Goal 推进决策 · 已核对输入。下一步生成报告。',
    'Goal 整体交付 · 已完成报告及复核。',
  ])
})

it('projects an autonomous Mission review as system progress and an exact assistant Attempt without a user instruction',()=>{
 const selected={...work('work_a','attempt_review'),conversationMode:true,messages:[]}
 const requested:EventEnvelope={...delta('attempt_review'),eventId:'evt_review',eventSeq:1,eventType:'mission_review_requested',payload:{mission_id:'goal_one',review_id:'review_one',work_id:'work_a',boundary:{digest:'a'.repeat(64),plan_revision:2,tasks:[]},source_origin:{thread_id:'thr_work'}}}
 const started={...requested,eventId:'evt_started',eventSeq:2,eventType:'attempt_started',payload:{work_id:'work_a'}}
 const rows=projectWorkConversation([requested,started],selected,[selected]).messages
 expect(rows.filter(row=>row.role==='user')).toEqual([])
 const notice=rows.find(row=>row.metadata?.custom?.systemNotice)
 expect(notice?.content).toBe('正在根据任务结果调整计划')
 expect(notice?.metadata?.custom?.eventId).toBe('evt_review')
 expect(rows.find(row=>row.id==='assistant-attempt_review')?.metadata?.custom).toMatchObject({attemptId:'attempt_review',missionReview:{missionId:'goal_one',reviewId:'review_one',eventId:'evt_review'}})
 const completed={...started,eventId:'evt_completed',eventSeq:3,eventType:'attempt_completed',payload:{work_id:'work_a',answer:'已评估任务结果'}}
 const restored=projectWorkConversation([requested,started,completed],selected,[selected]).messages
 expect(restored.find(row=>row.metadata?.custom?.systemNotice)?.content).toBe('任务结果复盘已结束')
 expect(restored.filter(row=>row.role==='user')).toEqual([])
})
