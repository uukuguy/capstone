import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import CapstoneAssistantThread, { projectAssistantMessages } from './CapstoneAssistantThread'
import type { EventEnvelope } from './threadProtocol'

afterEach(cleanup)

const event = (eventType: string, eventSeq: number, payload: Record<string, unknown>, attemptId?: string): EventEnvelope => ({
  eventId: `evt_${eventSeq}`, eventSeq, eventType, eventVersion: 1, threadId: 'thr_demo', runId: 'run_demo', attemptId,
  occurredAt: '2026-09-30T00:00:00Z', visibility: 'public', payload,
})

describe('CapstoneAssistantThread', () => {
  it('projects public command and harness deltas into assistant-ui messages', () => {
    const messages = projectAssistantMessages([
      event('command_accepted', 1, { kind: 'send_professional', payload: { text: '检查当前线路' } }),
      event('assistant_text_delta', 2, { text: '正在读取模型。' }, 'attempt_1'),
      event('assistant_text_delta', 3, { text: ' 已完成。' }, 'attempt_1'),
      event('attempt_completed', 4, {}, 'attempt_1'),
    ])

    expect(messages.map((message) => [message.role, message.content])).toEqual([
      ['user', '检查当前线路'], ['assistant', [{ type: 'text', text: '正在读取模型。 已完成。' }]],
    ])
    expect(messages[1].status).toEqual({ type: 'complete', reason: 'stop' })
  })

  it('renders the mainstream chat surface with the Capstone composer', () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_ordinary', payload: { text: '查看当前模型' } }),
      event('assistant_text_delta', 2, { text: '当前模型为 IEEE-39。' }, 'attempt_1'),
    ]} disabled={false} isRunning={true} activity={['工具已启动 · capstone-harness']} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByTestId('assistant-ui-chat')).toBeTruthy()
    expect(screen.getByText('查看当前模型')).toBeTruthy()
    expect(screen.getByText('当前模型为 IEEE-39。')).toBeTruthy()
    expect(screen.getByText(/工具已启动/)).toBeTruthy()
    expect(screen.getByRole('textbox', { name: 'Thread 指令' })).toBeTruthy()
  })
})
