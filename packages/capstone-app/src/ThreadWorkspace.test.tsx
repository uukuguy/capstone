import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import CapstoneAssistantThread from './CapstoneAssistantThread'

afterEach(() => { cleanup(); sessionStorage.clear() })

it('uses the existing chat and composer for persisted Work messages without execution or model controls', async () => {
  const send = vi.fn(async () => {})
  render(<CapstoneAssistantThread events={[]} projectedMessages={[{ id: 'work_one-message-0', role: 'user', content: '已保存的目标' }]}
    disabled={false} isRunning={false} activity={[]} onSend={send} onCancel={async () => {}}
    composerMode="text" emptyState={<p>描述工作目标</p>} runtimeStatus="已保存，未执行"
    composerLabel="任务目标" sendLabel="保存任务" />)
  expect(screen.getByText('已保存的目标')).toBeTruthy()
  expect(screen.queryByText('实时响应')).toBeNull()
  expect(screen.queryByRole('button', { name: '选择技能' })).toBeNull()
  fireEvent.change(screen.getByRole('textbox', { name: '任务目标' }), { target: { value: '补充资料' } })
  fireEvent.click(screen.getByRole('button', { name: '保存任务' }))
  await waitFor(() => expect(send).toHaveBeenCalledWith('automatic', '补充资料'))
  expect(screen.queryByText('正在生成回答…')).toBeNull()
})
