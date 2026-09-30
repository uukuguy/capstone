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
    expect(screen.getByRole('heading', { name: '对话 Thread' })).toBeTruthy()
    expect(screen.getByRole('img', { name: '工业专业框架与 AI 智能体应用的连接示意' })).toBeTruthy()
    expect(screen.getByRole('img', { name: '电网拓扑' })).toBeTruthy()
    expect(screen.getByText('CAPABILITY / EVIDENCE / CONTROL')).toBeTruthy()
    expect(screen.getByTestId('assistant-ui-chat')).toBeTruthy()
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '查看当前模型' } })
    expect((screen.getByRole('button', { name: '发送普通指令' }) as HTMLButtonElement).disabled).toBe(false)
    expect(screen.getByRole('button', { name: /IEEE-39 · 当前模型/ })).toBeTruthy()
  })

  it('submits a model switch from the grid pane through the Thread command path', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.change(screen.getByRole('combobox', { name: '目标电网模型' }), { target: { value: 'pypsa39' } })
    fireEvent.click(screen.getByRole('button', { name: '切换模型' }))

    expect(await screen.findByText('switch_model · accepted')).toBeTruthy()
  })

  it('keeps live cancellation visible while the grid pane is historical', async () => {
    render(<ThreadFixtureApp fixtureId="historical-live-attempt" />)

    expect(await screen.findByText('历史页 · 只读视图')).toBeTruthy()
    expect((screen.getByRole('button', { name: '取消当前计算' }) as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(screen.getAllByRole('button', { name: '返回当前模型' })[0])
    await waitFor(() => expect(screen.queryByText('历史页 · 只读视图')).toBeNull())
    expect(screen.getByRole('button', { name: /IEEE-39 · 当前模型/ })).toBeTruthy()
  })

  it('freezes conversation controls behind the resync gate', async () => {
    render(<ThreadFixtureApp fixtureId="resync-required" />)

    expect((await screen.findAllByText('需要重新同步')).length).toBeGreaterThan(0)
    expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: '重新同步' }) as HTMLButtonElement).disabled).toBe(false)
    expect(screen.queryByRole('button', { name: '发送普通指令' })).toBeNull()
  })

  it('exposes a new Attempt retry after interruption', async () => {
    render(<ThreadFixtureApp fixtureId="interrupted-attempt" />)

    expect(await screen.findByText('本次 Attempt 已中断')).toBeTruthy()
    expect((screen.getByRole('button', { name: '重试新 Attempt' }) as HTMLButtonElement).disabled).toBe(false)
    expect(screen.getByText(/line_12/)).toBeTruthy()
  })
})
