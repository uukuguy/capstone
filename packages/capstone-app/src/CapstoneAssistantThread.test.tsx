import { afterEach, describe, expect, it, vi } from 'vitest'
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
    expect(screen.getByLabelText('输入工具栏')).toBeTruthy()
    expect(screen.getByText('自动路由')).toBeTruthy()
    expect(screen.queryByRole('button', { name: '自动识别' })).toBeNull()
    expect(screen.queryByRole('button', { name: '专业分析' })).toBeNull()
    expect(screen.queryByText(/⌘\/Ctrl/)).toBeNull()
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
    expect(screen.queryByRole('button', { name: '重试本次指令' })).toBeNull()
    expect((screen.getByRole('button', { name: '发送指令' }) as HTMLButtonElement).disabled).toBe(true)
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
    expect(screen.getByRole('group', { name: '当前运行结果' }).textContent).toContain('1 份')
    expect(screen.queryByLabelText('当前运行证据')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '查看证据' }))
    expect(screen.getByLabelText('当前运行证据').textContent).toContain('evidence:run_1:powerflow')
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

  it('renders the admitted result card and keeps evidence behind its action', () => {
    const events = [
      event('command_accepted', 1, { kind: 'send_professional', payload: { text: '运行潮流' } }, 'attempt_cards'),
      event('attempt_completed', 2, {
        answer: '潮流已收敛。',
        result_refs: ['result:run_1:powerflow'],
        evidence_refs: ['evidence:run_1:powerflow'],
        admission: { mode: 'authority_backed', assurance: 'lineage_verified', admission_ref: 'admission:run_1' },
      }, 'attempt_cards'),
    ]
    expect((projectAssistantMessages(events)[1].metadata as { custom?: { admission?: unknown } }).custom?.admission).toEqual(expect.objectContaining({ mode: 'authority_backed' }))
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)

    expect(screen.getByRole('group', { name: '当前运行结果' })).toBeTruthy()
    expect(screen.queryByLabelText('当前运行证据')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '查看证据' }))
    expect(screen.getByLabelText('当前运行证据')).toBeTruthy()
    expect(screen.getByText('已准入')).toBeTruthy()
    expect(screen.getByText(/admission:run_1/)).toBeTruthy()
  })

  it('shows a terminal failure with the next action instead of a generation placeholder', () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '运行潮流' } }, 'attempt_failed'),
      event('attempt_failed', 2, { error_code: 'solver_failed', message: '潮流求解器未收敛。' }, 'attempt_failed'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} onRegenerate={async () => {}} />)

    expect(screen.getByText('执行失败')).toBeTruthy()
    expect(screen.getByText('潮流求解器未收敛。')).toBeTruthy()
    expect(screen.queryByText('正在生成回答…')).toBeNull()
    expect(screen.getByRole('button', { name: '重试本次指令' })).toBeTruthy()
  })

  it('retries the failed Attempt identity and hides retry while another Attempt runs', async () => {
    const onRegenerate = vi.fn().mockResolvedValue(undefined)
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '运行潮流' } }, 'attempt_failed'),
      event('attempt_failed', 2, { error_code: 'solver_failed' }, 'attempt_failed'),
    ]
    const { rerender } = render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} onRegenerate={onRegenerate} />)
    fireEvent.click(screen.getByRole('button', { name: '重试本次指令' }))
    await waitFor(() => expect(onRegenerate).toHaveBeenCalledWith('attempt_failed', '运行潮流'))
    rerender(<CapstoneAssistantThread events={events} disabled={true} isRunning={true} activity={[]} onSend={async () => {}} onCancel={async () => {}} onRegenerate={onRegenerate} />)
    expect(screen.queryByRole('button', { name: '重试本次指令' })).toBeNull()
  })

  it('keeps partial text but makes cancellation explicit and stops incomplete tool steps', () => {
    const events = [
      event('attempt_started', 1, {}, 'attempt_cancelled'),
      event('tool_started', 2, { tool_name: 'grid_context_open', tool_call_id: 'pending_tool' }, 'attempt_cancelled'),
      event('assistant_text_delta', 3, { text: '已读取部分模型。' }, 'attempt_cancelled'),
      event('attempt_cancelled', 4, {}, 'attempt_cancelled'),
    ]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByText('已读取部分模型。')).toBeTruthy()
    expect(screen.getByText('本次 Attempt 已取消')).toBeTruthy()
    expect(screen.getByText(/已取消 · 1 个步骤/)).toBeTruthy()
    expect(screen.queryByText(/已完成 1 个步骤/)).toBeNull()
  })

  it('projects tool ok=false as a failure and retains completed provenance', () => {
    const activities = projectAssistantActivity([
      event('tool_started', 1, { tool_call_id: 'call_fail', tool_name: 'grid_context_open', binding_id: 'grid', capability: 'context.open' }, 'attempt_1'),
      event('tool_completed', 2, { tool_call_id: 'call_fail', ok: false }, 'attempt_1'),
    ])
    expect(activities[0]).toMatchObject({ status: 'failed', label: '打开模型上下文', source: 'grid · context.open' })
  })

  it('does not label an old answer with the newly selected model', () => {
    const terminal = { ...event('attempt_completed', 1, { answer: '旧模型结果。', evidence_refs: ['evidence:old'], admission: { mode: 'authority_backed', assurance: 'lineage_verified' } }, 'attempt_old'), modelContextId: 'ctx_old' }
    render(<CapstoneAssistantThread events={[terminal]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}}
      modelSummary={{ modelId: 'pypsa39', implementationFamily: 'pypsa', modelRevision: 'new_revision', contextId: 'ctx_new' }} />)
    expect(screen.queryByText(/pypsa39/)).toBeNull()
    expect(screen.queryByText(/ctx_old/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '查看证据' }))
    expect(screen.getByText(/ctx_old/)).toBeTruthy()
  })

  it('does not render result or evidence references without current-run admission', () => {
    render(<CapstoneAssistantThread events={[
      event('attempt_completed', 1, { answer: '未准入回答。', result_refs: ['result:unadmitted'], evidence_refs: ['evidence:unadmitted'] }, 'attempt_unadmitted'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)

    expect(screen.queryByRole('group', { name: '当前运行结果' })).toBeNull()
    expect(screen.queryByRole('group', { name: '当前运行证据' })).toBeNull()
    expect(screen.queryByRole('button', { name: '查看证据' })).toBeNull()
  })

  it('carries attempt model context into a terminal result card when the terminal event omits it', () => {
    const started = { ...event('attempt_started', 1, {}, 'attempt_context'), modelContextId: 'ctx_current', selectionRevision: 'sel_4' }
    render(<CapstoneAssistantThread events={[
      started,
      event('attempt_completed', 2, { answer: '潮流已收敛。', result_refs: ['result:current'], evidence_refs: ['evidence:current'], admission: { mode: 'authority_backed', assurance: 'lineage_verified' } }, 'attempt_context'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}}
      modelSummary={{ modelId: 'ieee39', implementationFamily: 'pandapower', modelRevision: 'revision:current', contextId: 'ctx_current' }} />)

    expect(screen.getByText(/ieee39 · pandapower · revision revision:current/)).toBeTruthy()
  })

  it('allows drafting during a running attempt while keeping send unavailable', () => {
    render(<CapstoneAssistantThread events={[event('attempt_started', 1, {}, 'attempt_live')]} disabled={true} isRunning={true} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const input = screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement
    expect(input.disabled).toBe(false)
    fireEvent.change(input, { target: { value: '下一条指令草稿' } })
    expect(input.value).toBe('下一条指令草稿')
    expect(screen.queryByRole('button', { name: '发送指令' })).toBeNull()
    expect(screen.getByRole('button', { name: '停止生成' })).toBeTruthy()
  })

  it('submits pasted multiline composer text intact', async () => {
    const onSend = vi.fn().mockResolvedValue(undefined)
    render(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={onSend} onCancel={async () => {}} />)
    const input = screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement

    fireEvent.change(input, { target: { value: '第一行\n第二行' } })
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter', charCode: 13 })

    await waitFor(() => expect(onSend).toHaveBeenCalledWith('automatic', '第一行\n第二行'))
  })

  it('keeps a stable composer action footprint while the input is empty', async () => {
    render(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const input = screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement
    const send = screen.getByRole('button', { name: '发送指令' }) as HTMLButtonElement

    expect(send.disabled).toBe(true)
    fireEvent.change(input, { target: { value: '查看当前模型' } })
    expect(send.disabled).toBe(false)
  })

  it('keeps the composer input focused when the Thread is ready for input', () => {
    render(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(document.activeElement).toBe(screen.getByRole('textbox', { name: 'Thread 指令' }))
  })

  it('sends multiline text from the composer action', async () => {
    const onSend = vi.fn().mockResolvedValue(undefined)
    render(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={onSend} onCancel={async () => {}} />)
    const input = screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement

    fireEvent.change(input, { target: { value: '第一行\n第二行' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))

    await waitFor(() => expect(onSend).toHaveBeenCalledWith('automatic', '第一行\n第二行'))
  })
})
