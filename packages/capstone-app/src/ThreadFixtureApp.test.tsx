import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ThreadFixtureApp from './ThreadFixtureApp'

afterEach(cleanup)

describe('ThreadFixtureApp', () => {
  it('renders an idle Thread with the current IEEE-39 model and ordinary controls', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    expect(await screen.findByRole('region', { name: '电网模型区' })).toBeTruthy()
    expect(screen.getByText('电网分析工作台')).toBeTruthy()
    expect(screen.queryByText('CAPSTONE / AGENT WORKSPACE')).toBeNull()
    expect(screen.getByRole('heading', { name: '智能体对话' })).toBeTruthy()
    expect(screen.getByRole('img', { name: '工业专业框架与 AI 智能体应用的连接示意' })).toBeTruthy()
    expect(screen.getByRole('img', { name: '电网拓扑' })).toBeTruthy()
    expect(screen.getByText('CAPABILITY / EVIDENCE / CONTROL')).toBeTruthy()
    expect(screen.getByTestId('assistant-ui-chat')).toBeTruthy()
    expect(screen.getByText(/IEEE-39 有哪些母线和线路/)).toBeTruthy()
    expect(screen.getByText(/对 IEEE-39 执行一次交流潮流/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '筛查负载率最高的三条线路。' }))
    expect(await screen.findByText('Fixture 已接收自动指令：筛查负载率最高的三条线路。')).toBeTruthy()
    expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe('')
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '查看当前模型' } })
    expect((screen.getByRole('button', { name: '发送指令' }) as HTMLButtonElement).disabled).toBe(false)
    expect(screen.getByRole('button', { name: /IEEE-39 · 当前模型/ })).toBeTruthy()
  })

  it('keeps identifiers in a compact diagnostics disclosure instead of the main heading', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    expect(screen.getByText('THREAD')).toBeTruthy()
    expect(screen.queryByText('THREAD / RUN run_001')).toBeNull()
    expect(screen.getByRole('button', { name: '查看 Thread 详情' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '查看 Thread 详情' }))
    expect(screen.getByText('run_001')).toBeTruthy()
  })

  it('submits a model switch from the grid pane through the Thread command path', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.change(screen.getByRole('combobox', { name: '目标电网模型' }), { target: { value: 'pypsa39' } })
    fireEvent.click(screen.getByRole('button', { name: '切换模型' }))

    expect(await screen.findByText('switch_model · accepted')).toBeTruthy()
  })

  it('routes an explicit model-open phrase through the canonical switch command', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '打开 pypsa39' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))

    expect(await screen.findByText('已提交切换到 PyPSA-39，下一条指令将在该模型上下文中执行。')).toBeTruthy()
    expect(screen.queryByText('Fixture 已接收自动指令：打开 pypsa39')).toBeNull()
  })

  it('does not reopen the active model unless the user explicitly requests a fresh context', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '打开 ieee39' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    expect(await screen.findByText('当前模型已经是 IEEE-39，未重复打开。')).toBeTruthy()
    expect(screen.queryByText('switch_model · accepted')).toBeNull()

    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '重新打开 ieee39' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    expect(await screen.findByText('已提交重新打开 IEEE-39，将建立新的模型上下文。')).toBeTruthy()
  })

  it('keeps a longer open-and-analyze request as ordinary agent work', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    const request = '打开 IEEE-39 网络并解析线路 11 的端点。'
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: request } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))

    expect(await screen.findByText(`Fixture 已接收自动指令：${request}`)).toBeTruthy()
  })

  it('reports a short unknown Chinese model control instead of guessing', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '打开 不存在模型' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))

    expect(await screen.findByText('未找到注册模型“不存在模型”。可先查看模型目录，或使用左侧模型选择器。')).toBeTruthy()
    expect(screen.queryByText(/Fixture 已接收自动指令/)).toBeNull()
  })

  it('keeps an English analytical request on the ordinary route', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    const request = '打开 IEEE-39 network and analyze line 11'
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: request } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))

    expect(await screen.findByText(`Fixture 已接收自动指令：${request}`)).toBeTruthy()
  })

  it('renders catalog-driven Profiles in a compact control and submits one selection command', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.click(screen.getByRole('button', { name: '输入设置' }))
    fireEvent.click(screen.getByRole('button', { name: /选择 Profile/ }))
    expect(screen.getByText('Pandapower Static Analysis')).toBeTruthy()
    fireEvent.click(screen.getByRole('checkbox', { name: 'Pandapower Static Analysis' }))
    fireEvent.click(screen.getByRole('button', { name: '应用 Profile 选择' }))

    expect(await screen.findByText('replace_selection · accepted')).toBeTruthy()
  })

  it('keeps the trace control compact and independently togglable', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.click(screen.getByRole('button', { name: '输入设置' }))
    const trace = screen.getByRole('button', { name: '隐藏运行过程' })
    fireEvent.click(trace)
    expect(screen.getByRole('button', { name: '显示运行过程' })).toBeTruthy()
  })

  it('closes the flat input settings menu when focus moves outside it', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.click(screen.getByRole('button', { name: '输入设置' }))
    expect(document.querySelector('.thread-settings-menu[open]')).toBeTruthy()
    fireEvent.click(document.body)
    expect(document.querySelector('.thread-settings-menu[open]')).toBeNull()
  })

  it('projects a sent automatic instruction and fixture response into the chat', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '查看当前模型' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))

    expect(await screen.findByText('查看当前模型')).toBeTruthy()
    expect(await screen.findByText('Fixture 已接收自动指令：查看当前模型')).toBeTruthy()
  })

  it('keeps live cancellation in the composer while the grid pane is historical', async () => {
    render(<ThreadFixtureApp fixtureId="historical-live-attempt" />)

    expect(await screen.findByText('历史页 · 只读视图')).toBeTruthy()
    expect(screen.queryByRole('alert', { name: 'event stream is not contiguous' })).toBeNull()
    expect(screen.getByRole('button', { name: '停止生成' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '取消当前计算' })).toBeNull()
    expect(screen.queryByRole('button', { name: '打开回放' })).toBeNull()
    fireEvent.click(screen.getAllByRole('button', { name: '返回当前模型' })[0])
    await waitFor(() => expect(screen.queryByText('历史页 · 只读视图')).toBeNull())
    expect(screen.getByRole('button', { name: /IEEE-39 · 当前模型/ })).toBeTruthy()
  })

  it('freezes conversation controls behind the resync gate', async () => {
    render(<ThreadFixtureApp fixtureId="resync-required" />)

    expect((await screen.findAllByText('需要重新同步')).length).toBeGreaterThan(0)
    expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: '重新同步' }) as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByRole('button', { name: '发送指令' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('exposes a new Attempt retry after interruption', async () => {
    render(<ThreadFixtureApp fixtureId="interrupted-attempt" />)

    expect(await screen.findByText('本次 Attempt 已中断')).toBeTruthy()
    expect((screen.getByRole('button', { name: '重试新 Attempt' }) as HTMLButtonElement).disabled).toBe(false)
    expect(screen.getByText(/line_12/)).toBeTruthy()
  })
})
