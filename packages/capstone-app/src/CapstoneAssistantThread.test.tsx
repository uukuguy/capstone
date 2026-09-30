import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import CapstoneAssistantThread, { projectAssistantActivity, projectAssistantMessages } from './CapstoneAssistantThread'
import type { EventEnvelope } from './threadProtocol'

afterEach(cleanup)

const event = (eventType: string, eventSeq: number, payload: Record<string, unknown>, attemptId?: string, occurredAt = '2026-09-30T00:00:00Z'): EventEnvelope => ({
  eventId: `evt_${eventSeq}`, eventSeq, eventType, eventVersion: 1, threadId: 'thr_demo', runId: 'run_demo', attemptId,
  occurredAt, visibility: 'public', payload,
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

  it('shows an explicit processing state for an assistant message without text yet', () => {
    render(<CapstoneAssistantThread events={[
      event('assistant_text_delta', 1, { text: '' }, 'attempt_1'),
    ]} disabled={true} isRunning={true} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)

    expect(screen.getByText('正在生成回答…')).toBeTruthy()
  })

  it('shows tool activity and elapsed time as soon as an attempt starts', () => {
    const startedAt = new Date(Date.now() - 2300).toISOString()
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '读取当前模型' } }, 'attempt_live', startedAt),
      event('attempt_started', 2, {}, 'attempt_live', startedAt),
      event('tool_started', 3, { tool_name: 'grid_model_list', binding_id: 'grid', capability: 'model.list' }, 'attempt_live', new Date(Date.now() - 1200).toISOString()),
    ]
    const messages = projectAssistantMessages(events)
    expect(messages).toHaveLength(2)
    expect(messages[1].status).toEqual({ type: 'running' })
    expect((messages[1].metadata as { custom?: { activities?: unknown[] } }).custom?.activities).toEqual([
      expect.objectContaining({ id: 'grid_model_list', label: '读取模型目录', source: 'grid · model.list', status: 'running', startedAt: expect.any(String) }),
    ])
    render(<CapstoneAssistantThread events={events} disabled={true} isRunning={true} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByText((_, element) => element?.tagName === 'SPAN' && element.textContent?.includes('正在执行 1 个步骤') === true)).toBeTruthy()
    expect(screen.getAllByText(/运行中/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('读取模型目录')).toBeTruthy()
  })

  it('keeps the final attempt duration on the completed answer', () => {
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '查看当前模型' } }, 'attempt_timed', '2026-09-30T00:00:00.000Z'),
      event('attempt_started', 2, {}, 'attempt_timed', '2026-09-30T00:00:00.000Z'),
      event('attempt_completed', 3, { answer: '当前模型为 IEEE-39。' }, 'attempt_timed', '2026-09-30T00:00:02.345Z'),
    ]
    const messages = projectAssistantMessages(events)
    expect((messages[1].metadata as { custom?: { durationMs?: number } }).custom?.durationMs).toBe(2345)
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByText('运行 2.3s')).toBeTruthy()
  })

  it('projects the authoritative answer when the harness emits it on completion', () => {
    const messages = projectAssistantMessages([
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '查看当前模型' } }),
      event('attempt_completed', 2, { answer: '当前模型为 IEEE-39。' }, 'attempt_1'),
    ])

    expect(messages.map((message) => [message.role, message.content])).toEqual([
      ['user', '查看当前模型'],
      ['assistant', [{ type: 'text', text: '当前模型为 IEEE-39。' }]],
    ])
    expect(messages[1].status).toEqual({ type: 'complete', reason: 'stop' })
  })

  it('groups tool events into readable activity steps', () => {
    expect(projectAssistantActivity([
      event('tool_started', 1, { tool_name: 'grid_model_list', capability: 'model.list', binding_id: 'grid' }, 'attempt_1'),
      event('tool_completed', 2, { tool_name: 'grid_model_list', capability: 'model.list', binding_id: 'grid' }, 'attempt_1'),
      event('tool_started', 3, { tool_name: 'grid_context_get', capability: 'context.get', binding_id: 'grid' }, 'attempt_1'),
    ])).toEqual([
      expect.objectContaining({ id: 'grid_model_list', label: '读取模型目录', source: 'grid · model.list', status: 'completed', durationMs: 0 }),
      expect.objectContaining({ id: 'grid_context_get', label: '读取模型上下文', source: 'grid · context.get', status: 'running' }),
    ])
  })

  it('renders Markdown and mainstream message actions', async () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '查看当前模型' } }),
      event('attempt_completed', 2, { answer: '## 当前模型\n\n| 项目 | 值 |\n| --- | --- |\n| 母线 | 39 |' }, 'attempt_1'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} onRegenerate={async () => {}} />)

    expect(screen.getByRole('heading', { name: '当前模型' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: '当前模型' }).closest('.capstone-chat-markdown')).toBeTruthy()
    expect(screen.getByRole('cell', { name: '39' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '复制回答' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '重新运行回答' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '发送指令' })).toBeNull()
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '继续分析' } })
    expect(screen.getByRole('button', { name: '发送指令' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '编辑指令' }))
    await waitFor(() => expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe('查看当前模型'))
  })

  it('shows evidence actions only for admitted current-run references', () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '运行交流潮流' } }, 'attempt_1'),
      event('tool_started', 2, { tool_name: 'grid_context_open', capability: 'context.open', binding_id: 'grid' }, 'attempt_1'),
      event('tool_completed', 3, { tool_name: 'grid_context_open', capability: 'context.open', binding_id: 'grid' }, 'attempt_1'),
      event('attempt_completed', 4, { answer: '潮流已收敛。', result_refs: ['result:run_1:powerflow'], evidence_refs: ['evidence:run_1:powerflow'], admission: { status: 'admitted' } }, 'attempt_1'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} onRegenerate={async () => {}} />)

    expect(screen.getByRole('button', { name: '查看证据' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '查看运行过程' })).toBeTruthy()
    expect(screen.getByLabelText('当前运行结果引用').textContent).toContain('结果 1')
    expect(screen.getByLabelText('当前运行结果引用').textContent).toContain('证据 1')
    expect(screen.queryByText('evidence:run_1:powerflow')).toBeNull()
  })

  it('keeps repeated tool calls and each conversation activity separate', () => {
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '打开模型' } }, 'attempt_1'),
      event('tool_started', 2, { tool_name: 'grid_context_open', tool_call_id: 'call_a' }, 'attempt_1'),
      event('tool_completed', 3, { tool_name: 'grid_context_open', tool_call_id: 'call_a', binding_id: 'grid', capability: 'context.open' }, 'attempt_1'),
      event('attempt_completed', 4, { answer: '已打开模型。' }, 'attempt_1'),
      event('command_accepted', 5, { kind: 'send_auto', payload: { text: '运行潮流' } }, 'attempt_2'),
      event('tool_started', 6, { tool_name: 'grid_context_get', tool_call_id: 'call_b' }, 'attempt_2'),
      event('tool_completed', 7, { tool_name: 'grid_context_get', tool_call_id: 'call_b', binding_id: 'grid', capability: 'context.get' }, 'attempt_2'),
      event('tool_started', 8, { tool_name: 'grid_context_get', tool_call_id: 'call_c' }, 'attempt_2'),
      event('tool_completed', 9, { tool_name: 'grid_context_get', tool_call_id: 'call_c', binding_id: 'grid', capability: 'context.get' }, 'attempt_2'),
      event('attempt_completed', 10, { answer: '| 指标 | 值 |\n| --- | --- |\n| 收敛 | 是 |' }, 'attempt_2'),
    ]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={projectAssistantActivity(events)} onSend={async () => {}} onCancel={async () => {}} />)
    const first = screen.getByText('已打开模型。').closest('.capstone-chat-message')!
    const second = screen.getByRole('table').closest('.capstone-chat-message')!
    expect(within(first as HTMLElement).getByText('已完成 1 个步骤')).toBeTruthy()
    expect(within(second as HTMLElement).getByText('已完成 2 个步骤')).toBeTruthy()
    expect(first.querySelectorAll('details')).toHaveLength(1)
    expect(second.querySelectorAll('details')).toHaveLength(1)
    fireEvent.click(within(first as HTMLElement).getByRole('button', { name: '查看运行过程' }))
    expect(first.querySelector('details')?.open).toBe(true)
    expect(second.querySelector('details')?.open).toBe(false)
  })
})
