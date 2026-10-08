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
  it('keeps recovery available after a diagnostic cursor and excludes it from an older history page', () => {
    const props = { events: [event('attempt_completed', 2, { answer: '已完成回答' }, 'first')],
      systemNotices: [{ id: 'connection', afterEventSeq: 3, text: '连接需要恢复', tone: 'error' as const, action: 'reconnect' as const }],
      disabled: true, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {} }
    const { rerender } = render(<CapstoneAssistantThread {...props} />)
    expect(screen.getByRole('button', { name: '重新连接' })).toBeTruthy()
    rerender(<CapstoneAssistantThread {...props} historyAtLatest={false} />)
    expect(screen.queryByRole('button', { name: '重新连接' })).toBeNull()
  })

  it('positions local system notices between instructions and preserves them without answer actions', () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_auto', text: '第一条指令' }, 'first'),
      event('attempt_completed', 2, { answer: '第一条回答' }, 'first'),
      event('command_accepted', 3, { kind: 'send_auto', text: '第二条指令' }, 'second'),
      event('attempt_completed', 4, { answer: '第二条回答' }, 'second'),
    ]} systemNotices={[{ id: 'rejected', afterEventSeq: 2, text: '本次指令未发送，输入已保留。', tone: 'error' }]}
      disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const notice = screen.getByText('本次指令未发送，输入已保留。').closest('[data-message-id]') as HTMLElement
    expect(notice.classList.contains('is-system')).toBe(true)
    const nodes = [...document.querySelectorAll('[data-message-id]')]
    expect(nodes.indexOf(notice)).toBe(2)
    expect(within(notice).queryByRole('button', { name: '复制回答' })).toBeNull()
    expect(within(notice).queryByRole('button', { name: '查看分析证据' })).toBeNull()
  })

  it('shows a failure once as a system notice after any partial answer', () => {
    render(<CapstoneAssistantThread events={[
      event('assistant_text_delta', 1, { text: '尚未完成的分析说明。' }, 'failed'),
      event('attempt_failed', 2, { error_code: 'solver_failed' }, 'failed'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByText('尚未完成的分析说明。')).toBeTruthy()
    const failure = screen.getByText('执行失败').closest('.capstone-system-notice')
    expect(failure).toBeTruthy()
    expect(screen.getAllByText('执行失败')).toHaveLength(1)
  })
  it('keeps evidence actions visible and distinguishes all five contract states', () => {
    render(<CapstoneAssistantThread events={[
      event('attempt_completed', 1, { answer: '有已准入证据。', evidence_refs: ['evidence:1'], admission: { mode: 'authority_backed', assurance: 'lineage_verified' } }, 'available'),
      event('attempt_completed', 2, { answer: '普通信息回答。', admission: { mode: 'offline_information', assurance: 'general_knowledge' } }, 'information'),
      event('attempt_failed', 3, { error_code: 'capability_required' }, 'missing'),
      event('attempt_failed', 4, { error_code: 'answer_admission_failed' }, 'unavailable'),
      event('assistant_text_delta', 5, { text: '还在计算。' }, 'pending'),
    ]} disabled={false} isRunning={true} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const actions = screen.getAllByRole('button', { name: '查看证据' }) as HTMLButtonElement[]
    expect(actions.map((action) => action.dataset.evidenceState)).toEqual(['available', 'not_applicable', 'missing', 'unavailable', 'pending'])
    expect(actions.map((action) => action.disabled)).toEqual([false, true, true, true, true])
    expect(actions.map((action) => action.title)).toEqual(['查看证据', '普通信息回答无需运行证据', '缺少所需证据', '证据暂不可用', '证据同步中'])
    fireEvent.click(actions[0])
    expect(screen.getByRole('region', { name: '当前运行证据' }).textContent).toContain('evidence:1')
  })
  it('uses the committed answer instead of provisional streamed text', () => {
    const messages = projectAssistantMessages([
      event('assistant_text_delta', 1, { text: '临时不完整回答。' }, 'attempt_1'),
      event('attempt_completed', 2, { answer: '完整正式回答。', answer_summary: '正式回答。' }, 'attempt_1'),
    ])
    expect(messages[0].content).toEqual([{ type: 'text', text: '完整正式回答。' }])
    expect(messages[0].metadata?.custom?.answerSummary).toBeUndefined()
  })

  it('organizes existing answers once and leaves new answers and drafts intact', () => {
    const answer = '已有结论。\n\n' + '完整条件。'.repeat(160)
    const onSend = vi.fn()
    const props = { events: [event('attempt_completed', 1, { answer }, 'attempt_1')], disabled: false, isRunning: false, activity: [], onSend, onCancel: async () => {} }
    const { rerender } = render(<CapstoneAssistantThread {...props} storageKey="reading_thread" />)
    const input = screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: '下一条草稿' } })
    expect(screen.queryByRole('combobox', { name: '回答显示模式' })).toBeNull()
    const menu = screen.getByRole('button', { name: '对话设置' })
    expect(menu.closest('.capstone-composer-footer')).toBeTruthy()
    const first = screen.getByText(/完整条件。完整条件/).closest('.capstone-chat-message')!
    expect(within(first as HTMLElement).getByRole('button', { name: '折叠回答' }).getAttribute('aria-expanded')).toBe('true')
    fireEvent.click(menu)
    fireEvent.click(screen.getByRole('button', { name: '折叠历史回答' }))
    expect(first.querySelector('.capstone-answer-content')?.getAttribute('aria-hidden')).toBe('true')
    rerender(<CapstoneAssistantThread {...props} storageKey="reading_thread" events={[
      ...props.events, event('attempt_completed', 2, { answer: '后续结论。\n\n' + '后续条件。'.repeat(160) }, 'attempt_2'),
    ]} />)
    expect(screen.getByText('后续结论。')).toBeTruthy()
    expect(screen.getByText(/后续条件。后续条件/).closest('.capstone-answer-content')?.getAttribute('aria-hidden')).toBeNull()
    expect(within(first as HTMLElement).getByRole('button', { name: '展开完整回答' })).toBeTruthy()
    fireEvent.click(within(first as HTMLElement).getByRole('button', { name: '展开完整回答' }))
    fireEvent.click(within(first as HTMLElement).getByRole('button', { name: '折叠回答' }))
    fireEvent.click(menu)
    fireEvent.click(screen.getByRole('button', { name: '展开历史回答' }))
    expect(screen.getAllByRole('button', { name: '折叠回答' })).toHaveLength(2)
    expect(input.value).toBe('下一条草稿')
    expect(onSend).not.toHaveBeenCalled()
  })

  it('ignores old mode preferences and keeps short answers and failure recovery visible', () => {
    sessionStorage.setItem('old_reading.readingMode', 'compact')
    render(<CapstoneAssistantThread events={[
      event('attempt_completed', 1, { answer: '没有摘要的正式回答。' }, 'attempt_1'),
      event('attempt_completed', 2, { answer: '保留正式事实。', answer_summary: '额外虚构数值。' }, 'attempt_2'),
      event('assistant_text_delta', 3, { text: '进行中。'.repeat(100) }, 'pending'),
      event('attempt_failed', 4, { error_code: 'capability_required' }, 'failed'),
    ]} storageKey="old_reading" disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    fireEvent.click(screen.getByRole('button', { name: '折叠历史回答' }))
    expect(screen.getByText('没有摘要的正式回答。')).toBeTruthy()
    expect(screen.getByText('保留正式事实。')).toBeTruthy()
    expect(screen.queryByText('额外虚构数值。')).toBeNull()
    expect(screen.queryByRole('button', { name: '展开完整回答' })).toBeNull()
    expect(screen.getByText(/进行中。进行中/)).toBeTruthy()
    expect(screen.getByText(/本次回答缺少所需的权威系统校验/)).toBeTruthy()
    sessionStorage.removeItem('old_reading.readingMode')
  })

  it('anchors repeated history actions to the visible instruction instead of the preceding long answer', () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_auto', text: '之前的指令' }, 'first'),
      event('attempt_completed', 2, { answer: '之前的长回答。'.repeat(100) }, 'first'),
      event('command_accepted', 3, { kind: 'send_auto', text: '当前阅读的指令' }, 'second'),
      event('attempt_completed', 4, { answer: '当前的长回答。'.repeat(100) }, 'second'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const viewport = document.querySelector('.capstone-chat-viewport') as HTMLElement
    const preceding = document.querySelector('[data-message-id="assistant-first"]') as HTMLElement
    const question = document.querySelector('[data-message-id="user-evt_3"]') as HTMLElement
    const current = document.querySelector('[data-message-id="assistant-second"]') as HTMLElement
    const rect = (top: number, height: number) => ({ top, bottom: top + height, height, left: 0, right: 500, width: 500, x: 0, y: top, toJSON: () => ({}) })
    viewport.scrollTop = 5000
    Object.defineProperties(viewport, { clientHeight: { value: 500 }, scrollHeight: { value: 20000 } })
    vi.spyOn(viewport, 'getBoundingClientRect').mockImplementation(() => rect(0, 500))
    const folded = () => preceding.querySelector('.capstone-answer')?.getAttribute('data-answer-state') === 'collapsed'
    vi.spyOn(preceding, 'getBoundingClientRect').mockImplementation(() => rect(50 - viewport.scrollTop, folded() ? 250 : 5050))
    vi.spyOn(question, 'getBoundingClientRect').mockImplementation(() => rect((folded() ? 300 : 5100) - viewport.scrollTop, 40))
    vi.spyOn(current, 'getBoundingClientRect').mockImplementation(() => rect((folded() ? 360 : 5160) - viewport.scrollTop, folded() ? 250 : 5000))
    const menu = screen.getByRole('button', { name: '对话设置' })
    viewport.scrollTop = 6000
    fireEvent.click(menu)
    fireEvent.click(screen.getByRole('button', { name: '展开历史回答' }))
    expect(viewport.scrollTop).toBe(6000)
    viewport.scrollTop = 5000
    for (const fold of [true, false, true, true, false, false]) {
      fireEvent.click(menu)
      fireEvent.click(screen.getByRole('button', { name: fold ? '折叠历史回答' : '展开历史回答' }))
      expect(question.getBoundingClientRect().top).toBe(100)
      expect(document.activeElement).toBe(menu)
    }
    viewport.scrollTop -= 50
    fireEvent.click(menu)
    fireEvent.click(screen.getByRole('button', { name: '折叠历史回答' }))
    expect(question.getBoundingClientRect().top).toBe(150)
  })

  it('copies the full committed answer while its display is folded', async () => {
    const answer = '结论。\n\n' + '完整条件。'.repeat(160)
    const copy = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: copy } })
    render(<CapstoneAssistantThread events={[event('attempt_completed', 1, { answer, answer_summary: '结论。' }, 'attempt_1')]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    fireEvent.click(screen.getByRole('button', { name: '折叠回答' }))
    fireEvent.click(screen.getByRole('button', { name: '复制回答' }))
    await waitFor(() => expect(copy).toHaveBeenCalledWith(answer))
  })

  it('does not fold an answer that completes after a bulk action', () => {
    const first = event('attempt_completed', 1, { answer: '历史回答。'.repeat(100) }, 'first')
    const pending = event('assistant_text_delta', 2, { text: '生成中。'.repeat(100) }, 'pending')
    const props = { events: [first, pending], disabled: false, isRunning: true, activity: [], onSend: async () => {}, onCancel: async () => {} }
    const { rerender } = render(<CapstoneAssistantThread {...props} />)
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    fireEvent.click(screen.getByRole('button', { name: '折叠历史回答' }))
    rerender(<CapstoneAssistantThread {...props} isRunning={false} events={[first, pending, event('attempt_completed', 3, { answer: '新完成回答。'.repeat(100) }, 'pending')]} />)
    expect(screen.getAllByRole('button', { name: '展开完整回答' })).toHaveLength(1)
    expect(screen.getAllByRole('button', { name: '折叠回答' })).toHaveLength(1)
  })

  it('clears folding when switching Threads or refreshing instead of saving a global preference', () => {
    const props = { events: [event('attempt_completed', 1, { answer: '完整回答。'.repeat(100) }, 'first')], disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {} }
    const { rerender, unmount } = render(<CapstoneAssistantThread {...props} storageKey="fold_thread_a" />)
    fireEvent.click(screen.getByRole('button', { name: '折叠回答' }))
    expect(screen.getByRole('button', { name: '展开完整回答' })).toBeTruthy()
    rerender(<CapstoneAssistantThread {...props} storageKey="fold_thread_b" />)
    expect(screen.getByRole('button', { name: '折叠回答' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '折叠回答' }))
    unmount()
    render(<CapstoneAssistantThread {...props} storageKey="fold_thread_b" />)
    expect(screen.getByRole('button', { name: '折叠回答' })).toBeTruthy()
    expect(sessionStorage.getItem('fold_thread_b.readingMode')).toBeNull()
  })

  it('folds loaded answers outside the visible message window and retains individual overrides', () => {
    const events = Array.from({ length: 60 }, (_, index) => event('attempt_completed', index + 1, { answer: `历史 ${index}。` + '完整条件。'.repeat(100) }, `history_${index}`))
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    fireEvent.click(screen.getByRole('button', { name: '折叠历史回答' }))
    expect(screen.getAllByRole('button', { name: '展开完整回答' })).toHaveLength(50)
    fireEvent.click(screen.getAllByRole('button', { name: '展开完整回答' }).at(-1)!)
    fireEvent.click(screen.getByRole('button', { name: '查看之前的对话' }))
    expect(screen.getAllByRole('button', { name: '展开完整回答' }).length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: '折叠回答' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '返回最新对话' }))
    expect(screen.getAllByRole('button', { name: '折叠回答' })).toHaveLength(1)
    expect(screen.getAllByRole('button', { name: '展开完整回答' })).toHaveLength(49)
  })

  it('closes the history actions on Escape and outside clicks', () => {
    render(<CapstoneAssistantThread events={[event('attempt_completed', 1, { answer: '历史回答。' }, 'first')]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const button = screen.getByRole('button', { name: '对话设置' })
    fireEvent.click(button)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(button.getAttribute('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(button)
    fireEvent.click(button)
    fireEvent.pointerDown(document.body)
    expect(screen.queryByRole('group', { name: '历史回答整理' })).toBeNull()
  })

  it('keeps one persistent answer toggle and its focus through collapse and expansion', () => {
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', text: '检查这条用户指令的回答' }, 'first'),
      event('attempt_completed', 2, { answer: '完整回答。'.repeat(160) }, 'first'),
    ]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(projectAssistantMessages(events)[1].metadata?.custom?.instructionMessageId).toBe('user-evt_1')
    const toggle = screen.getByRole('button', { name: '折叠回答' })
    expect(toggle.textContent).toBe('')
    expect(toggle.title).toBe('收起回答')
    expect(toggle.closest('.capstone-answer-header')?.querySelector('.capstone-chat-role')?.textContent).toBe('CAPSTONE')
    toggle.focus()
    fireEvent.click(toggle)
    const folded = screen.getByRole('button', { name: '展开完整回答' }).closest('.capstone-answer')!
    expect(folded.getAttribute('data-answer-state')).toBe('collapsed')
    expect(within(folded as HTMLElement).queryByText('已折叠')).toBeNull()
    expect(screen.getByRole('button', { name: '展开完整回答' })).toBe(toggle)
    expect(toggle.title).toBe('展开完整回答')
    expect(document.activeElement).toBe(toggle)
    fireEvent.click(toggle)
    expect(document.activeElement).toBe(toggle)
    expect(screen.getAllByRole('button', { name: '折叠回答' })).toEqual([toggle])
    expect(screen.queryByRole('button', { name: '折叠回答并返回指令' })).toBeNull()
  })

  it('reveals the corresponding loaded instruction while retaining toggle focus', () => {
    const events = [event('command_accepted', 1, { kind: 'send_auto', text: '窗口边界的用户指令' }, 'first'), event('attempt_completed', 2, { answer: '边界回答。'.repeat(160) }, 'first'), ...Array.from({length:49}, (_, i) => event('attempt_completed', i + 3, { answer: `其他回答 ${i}` }, `other_${i}`))]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.queryByText('窗口边界的用户指令')).toBeNull()
    const toggle = screen.getByRole('button', { name: '折叠回答' })
    toggle.focus()
    fireEvent.click(toggle)
    expect(screen.getByText('窗口边界的用户指令')).toBeTruthy()
    expect(document.activeElement?.getAttribute('aria-label')).toBe('展开完整回答')
  })

  it('keeps toggle focus when its instruction is not loaded instead of choosing another question', () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_auto', text: '无关用户指令' }, 'other'),
      event('attempt_completed', 2, { answer: '原始指令未加载的回答。'.repeat(100) }, 'missing_instruction'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const toggle = screen.getByRole('button', { name: '折叠回答' })
    toggle.focus()
    fireEvent.click(toggle)
    expect(document.activeElement).toBe(toggle)
  })
  it('clears a reconciled draft once and preserves a later draft', async () => {
    const props = { events: [], disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {} }
    const { rerender } = render(<CapstoneAssistantThread {...props} />)
    const input = screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: '已提交指令' } })
    const acceptedDraft = { text: '已提交指令', commandId: 'cmd_recovered' }
    rerender(<CapstoneAssistantThread {...props} acceptedDraft={acceptedDraft} />)
    await waitFor(() => expect(input.value).toBe(''))
    fireEvent.change(input, { target: { value: '下一条草稿' } })
    rerender(<CapstoneAssistantThread {...props} acceptedDraft={{ ...acceptedDraft }} />)
    expect(input.value).toBe('下一条草稿')
    rerender(<CapstoneAssistantThread {...props} acceptedDraft={{ text: '其他已提交指令', commandId: 'cmd_other' }} />)
    expect(input.value).toBe('下一条草稿')
  })
  it('disables a completed rerun when a new instruction is blocked or its model context is historical', () => {
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '运行潮流' } }, 'attempt_1'),
      { ...event('attempt_completed', 2, { answer: '已完成。' }, 'attempt_1'), modelContextId: 'ctx_old' },
    ]
    const onRegenerate = vi.fn()
    const props = { events, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {}, onRegenerate }
    const { rerender } = render(<CapstoneAssistantThread {...props} disabled={true} />)
    expect((screen.getByRole('button', { name: '重试本次指令' }) as HTMLButtonElement).disabled).toBe(true)
    rerender(<CapstoneAssistantThread {...props} disabled={false}
      modelSummary={{ modelId: 'case57', implementationFamily: 'pandapower', modelRevision: 'new', contextId: 'ctx_new' }} />)
    const retry = screen.getByRole('button', { name: '重试本次指令' })
    expect((retry as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(retry)
    expect(onRegenerate).not.toHaveBeenCalled()
  })
  it('keeps common answer actions in the same order and disables unavailable actions', () => {
    render(<CapstoneAssistantThread events={[
      event('attempt_completed', 1, { answer: '目录信息。' }, 'attempt_catalog'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const toolbar = screen.getByLabelText('回答操作')
    const buttons = within(toolbar).getAllByRole('button')
    expect(buttons.map((button) => button.getAttribute('aria-label'))).toEqual([
      '复制回答', '查看此指令电网图', '查看分析结果', '查看证据', '查看运行过程', '重试本次指令', '更多回答操作',
    ])
    expect(buttons.map((button) => (button as HTMLButtonElement).disabled)).toEqual([
      false, true, true, true, true, true, false,
    ])
    buttons.slice(1, 6).forEach((button) => fireEvent.click(button))
    expect(screen.queryByLabelText('当前运行证据')).toBeNull()
    expect(screen.queryByLabelText('本次运行过程')).toBeNull()
  })
  it('keeps unfinished feedback actions disabled inside More', async () => {
    render(<CapstoneAssistantThread events={[
      event('attempt_completed', 1, { answer: '已读取模型。' }, 'attempt_1'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByRole('button', { name: '复制回答' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '回答有帮助' })).toBeNull()
    expect(screen.queryByRole('button', { name: '回答需改进' })).toBeNull()
    const more = screen.getByRole('button', { name: '更多回答操作' })
    fireEvent.click(more)
    const group = screen.getByRole('group', { name: '更多回答操作' })
    expect(within(group).getByRole('button', { name: /回答有帮助/ }).hasAttribute('disabled')).toBe(true)
    expect(within(group).getByRole('button', { name: /回答需改进/ }).hasAttribute('disabled')).toBe(true)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('group', { name: '更多回答操作' })).toBeNull()
    expect(document.activeElement).toBe(more)
    fireEvent.click(more)
    fireEvent.pointerDown(screen.getByRole('textbox', { name: 'Thread 指令' }))
    expect(screen.queryByRole('group', { name: '更多回答操作' })).toBeNull()
  })
  it('selects only the grid view belonging to that answer', async () => {
    const selected = vi.fn()
    render(<CapstoneAssistantThread events={[
      event('attempt_completed', 1, { answer: '全网潮流' }, 'attempt_flow'),
      event('attempt_completed', 2, { answer: '前三条线路' }, 'attempt_rank'),
      event('attempt_completed', 3, { answer: '目录信息' }, 'attempt_catalog'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}}
      networkAttemptIds={['attempt_flow', 'attempt_rank']} onShowNetwork={selected} />)
    const actions = await screen.findAllByRole('button', { name: '查看此指令电网图' })
    expect(actions).toHaveLength(3)
    expect((actions[0] as HTMLButtonElement).disabled).toBe(false)
    expect((actions[1] as HTMLButtonElement).disabled).toBe(false)
    expect((actions[2] as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(actions[2])
    expect(selected).not.toHaveBeenCalled()
    fireEvent.click(actions[0])
    expect(selected).toHaveBeenLastCalledWith('attempt_flow')
    fireEvent.click(actions[1])
    expect(selected).toHaveBeenLastCalledWith('attempt_rank')
  })
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
    expect(screen.getByRole('button', { name: '对话设置' })).toBeTruthy()
    expect(screen.queryByText('自动路由')).toBeNull()
    expect(screen.queryByRole('button', { name: '自动识别' })).toBeNull()
    expect(screen.queryByRole('button', { name: '专业分析' })).toBeNull()
    expect(screen.queryByText(/⌘\/Ctrl/)).toBeNull()
  })

  it('puts the cross-family model questions first in the empty-thread suggestions', () => {
    render(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)

    expect(within(screen.getByLabelText('示例问题')).getAllByRole('button').map((button) => button.textContent)).toEqual([
      '有哪些 PyPSA 的电网模型？',
      '有哪些 pandapower 的电网模型？',
      'IEEE-39 有哪些母线和线路？',
      '对 IEEE-39 执行一次交流潮流。',
      '筛查负载率最高的三条线路。',
    ])
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
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '查看当前模型' } }, 'attempt_1'),
      event('attempt_completed', 2, { answer: '## 当前模型\n\n| 项目 | 值 |\n| --- | --- |\n| 母线 | 39 |' }, 'attempt_1'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} onRegenerate={async () => {}} />)

    expect(screen.getByRole('heading', { name: '当前模型' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: '当前模型' }).closest('.capstone-chat-markdown')).toBeTruthy()
    expect(screen.getByRole('cell', { name: '39' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '复制回答' })).toBeTruthy()
    expect((screen.getByRole('button', { name: '重试本次指令' }) as HTMLButtonElement).disabled).toBe(false)
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
    expect(screen.getByRole('status').textContent).toContain('1 项结构化结果')
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

    expect(screen.getByRole('status').textContent).toContain('1 项结构化结果')
    expect(screen.queryByLabelText('当前运行证据')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '查看证据' }))
    expect(screen.getByLabelText('当前运行证据')).toBeTruthy()
    expect(screen.getByRole('status').textContent).toContain('已准入')
    expect(screen.queryByText(/admission:run_1/)).toBeNull()
  })

  it('renders a structured result projection and can focus a topology element', () => {
    const onFocusElement = vi.fn()
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_professional', payload: { text: '筛查线路' } }, 'attempt_result'),
      event('attempt_completed', 2, { answer: '已完成线路筛查。' }, 'attempt_result'),
    ]} resultProjections={[{
      resultId: 'result_projection_1', resultRef: `result:sha256:${'a'.repeat(64)}`, evidenceRefs: [`evidence:sha256:${'b'.repeat(64)}`],
      threadId: 'thr_demo', runId: 'run_demo', turnId: 'turn_1', attemptId: 'attempt_result', modelContextId: 'ctx_demo', modelId: 'ieee39', modelRevision: `revision:sha256:${'c'.repeat(64)}`,
      source: { capabilityId: 'analysis.powerflow.ac.run', domainPackId: 'pandapower-static-analysis', implementationFamily: 'pandapower' }, status: 'completed',
      summary: [{ metricId: 'total_active_loss', label: '有功损耗', value: 43.64, unit: 'MW' }],
      tables: [{ tableId: 'line_loading', title: '线路负载率', columns: [{ columnId: 'line', label: '线路' }, { columnId: 'loading_percent', label: '负载率', unit: '%' }], rows: [{ rowId: 'line:11', cells: { line: '线路 11', loading_percent: 67.15 }, elementRef: { elementKind: 'line', elementId: 'line:11' } }] }],
      elementRefs: [{ elementKind: 'line', elementId: 'line:11' }], overlay: { metric: 'loading_percent', unit: '%', sourceRef: `result:sha256:${'a'.repeat(64)}`, values: [{ elementId: 'line:11', value: 67.15 }] },
    }, {
      resultId: 'result_projection_2', resultRef: `result:sha256:${'d'.repeat(64)}`, evidenceRefs: [`evidence:sha256:${'e'.repeat(64)}`],
      threadId: 'thr_demo', runId: 'run_demo', turnId: 'turn_1', attemptId: 'attempt_result', modelContextId: 'ctx_demo', modelId: 'ieee39', modelRevision: `revision:sha256:${'c'.repeat(64)}`,
      source: { capabilityId: 'analysis.powerflow.ac.run', domainPackId: 'pandapower-static-analysis', implementationFamily: 'pandapower' }, status: 'completed',
      summary: [{ metricId: 'total_active_loss_2', label: '电压偏差', value: 0.02, unit: 'pu' }], tables: [], elementRefs: [],
    }]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} onFocusElement={onFocusElement} />)

    fireEvent.click(screen.getByRole('button', { name: '查看分析结果' }))
    expect(screen.getAllByRole('region', { name: '结构化分析结果' })).toHaveLength(2)
    expect(screen.getByText('有功损耗')).toBeTruthy()
    expect(screen.getByText('电压偏差')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '线路 11' }))
    expect(onFocusElement).toHaveBeenCalledWith(expect.objectContaining({ resultId: 'result_projection_1' }), 'line:11')
  })

  it('shows configuration repair guidance for a runtime configuration failure', () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '有哪些 PyPSA 的电网模型？' } }, 'attempt_configuration'),
      event('attempt_failed', 2, { error_code: 'runtime_configuration_invalid' }, 'attempt_configuration'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByText('执行失败')).toBeTruthy()
    expect(screen.getByText(/服务的 AI 配置未就绪/)).toBeTruthy()
    expect(screen.getByText(/联系管理员检查配置，修复后再重试/)).toBeTruthy()
    expect(screen.queryByText(/能力上下文准备失败/)).toBeNull()
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

  it('retries the failed Attempt identity and disables retry while another Attempt runs', async () => {
    const onRegenerate = vi.fn().mockResolvedValue(undefined)
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '运行潮流' } }, 'attempt_failed'),
      event('attempt_failed', 2, { error_code: 'solver_failed' }, 'attempt_failed'),
    ]
    const { rerender } = render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} onRegenerate={onRegenerate} />)
    fireEvent.click(screen.getByRole('button', { name: '重试本次指令' }))
    await waitFor(() => expect(onRegenerate).toHaveBeenCalledWith('attempt_failed', '运行潮流'))
    rerender(<CapstoneAssistantThread events={events} disabled={true} isRunning={true} activity={[]} onSend={async () => {}} onCancel={async () => {}} onRegenerate={onRegenerate} />)
    const retry = screen.getByRole('button', { name: '重试本次指令' })
    expect((retry as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(retry)
    expect(onRegenerate).toHaveBeenCalledTimes(1)
  })

  it('keeps interrupted retry available while hiding terminal activity when trace is off', async () => {
    const onRegenerate = vi.fn().mockResolvedValue(undefined)
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '继续分析' } }, 'attempt_interrupted'),
      event('tool_completed', 2, { tool_name: 'grid_context_get', capability: 'context.get', binding_id: 'grid' }, 'attempt_interrupted'),
      event('assistant_text_delta', 3, { text: '已完成部分分析。' }, 'attempt_interrupted'),
      event('attempt_interrupted', 4, {}, 'attempt_interrupted'),
    ]
    render(<CapstoneAssistantThread events={events} disabled={true} isRunning={false} activity={[]} showActivity={false} onSend={async () => {}} onCancel={async () => {}} onRegenerate={onRegenerate} />)
    expect(screen.getByRole('button', { name: '重试本次指令' })).toBeTruthy()
    expect((screen.getByRole('button', { name: '查看运行过程' }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: '重试本次指令' }))
    await waitFor(() => expect(onRegenerate).toHaveBeenCalledWith('attempt_interrupted', '继续分析'))
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

  it('marks an interrupted run summary with the danger state', () => {
    render(<CapstoneAssistantThread events={[
      event('attempt_started', 1, {}, 'attempt_interrupted'),
      event('tool_started', 2, { tool_name: 'grid_context_open', binding_id: 'grid', capability: 'context.open' }, 'attempt_interrupted'),
      event('attempt_interrupted', 3, {}, 'attempt_interrupted'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)

    const summary = screen.getByText(/已中断 · 1 个步骤/)
    expect(summary.closest('details')?.classList.contains('is-interrupted')).toBe(true)
  })

  it('keeps a terminal-only interrupted replay visibly dangerous', () => {
    render(<CapstoneAssistantThread events={[
      event('tool_completed', 1, { tool_name: 'grid_context_open', binding_id: 'grid', capability: 'context.open' }, 'attempt_terminal_only'),
      event('attempt_interrupted', 2, {}, 'attempt_terminal_only'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)

    const summary = screen.getByText(/已中断 · 1 个步骤/)
    expect(summary.closest('details')?.classList.contains('is-interrupted')).toBe(true)
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

    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.queryByRole('group', { name: '当前运行证据' })).toBeNull()
    const evidence = screen.getByRole('button', { name: '查看证据' })
    expect((evidence as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(evidence)
    expect(screen.queryByLabelText('当前运行证据')).toBeNull()
  })

  it('carries attempt model context into a terminal result card when the terminal event omits it', () => {
    const started = { ...event('attempt_started', 1, {}, 'attempt_context'), modelContextId: 'ctx_current', selectionRevision: 'sel_4' }
    render(<CapstoneAssistantThread events={[
      started,
      event('attempt_completed', 2, { answer: '潮流已收敛。', result_refs: ['result:current'], evidence_refs: ['evidence:current'], admission: { mode: 'authority_backed', assurance: 'lineage_verified' } }, 'attempt_context'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}}
      modelSummary={{ modelId: 'ieee39', implementationFamily: 'pandapower', modelRevision: 'revision:current', contextId: 'ctx_current' }} />)

    expect(screen.getByRole('status').textContent).toContain('1 项结构化结果')
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
