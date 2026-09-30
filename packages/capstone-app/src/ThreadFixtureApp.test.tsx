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
