import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import CapstoneAssistantThread from './CapstoneAssistantThread'
import ThreadWorkspace from './ThreadWorkspace'

afterEach(() => { cleanup(); sessionStorage.clear() })

it('clamps a narrow window without replacing the preferred split and can reset it', () => {
  localStorage.clear()
  let width=1600
  const rect=vi.spyOn(HTMLElement.prototype,'getBoundingClientRect').mockImplementation(()=>({x:0,y:0,left:0,top:0,width,height:800,right:width,bottom:800,toJSON:()=>({})}))
  render(<ThreadWorkspace conversationOnly resourcePanel={<p>结果表</p>} resourcePanelOpen><p>对话</p></ThreadWorkspace>)
  const separator=screen.getByRole('separator')
  fireEvent.keyDown(separator,{key:'End'})
  expect(separator.getAttribute('aria-valuenow')).toBe('70')
  width=800;fireEvent.resize(window)
  expect(Number(separator.getAttribute('aria-valuenow'))).toBeLessThan(70)
  expect(localStorage.getItem('capstone.workspace.conversation-share')).toBe('70')
  width=1600;fireEvent.resize(window)
  expect(separator.getAttribute('aria-valuenow')).toBe('70')
  fireEvent.click(screen.getByRole('button',{name:'恢复默认比例'}))
  expect(separator.getAttribute('aria-valuenow')).toBe('67')
  rect.mockRestore();localStorage.clear()
})

it('bounds pointer resizing and keeps the split when the product workspace is expanded', () => {
  localStorage.clear()
  vi.stubGlobal('PointerEvent', MouseEvent)
  const rect=vi.spyOn(HTMLElement.prototype,'getBoundingClientRect').mockReturnValue({x:0,y:0,left:0,top:0,width:1000,height:800,right:1000,bottom:800,toJSON:()=>({})})
  const parentMove=vi.fn()
  render(<div onPointerMove={parentMove}><ThreadWorkspace conversationOnly resourcePanel={<p>结果表</p>} resourcePanelOpen><p>对话</p></ThreadWorkspace></div>)
  const separator=screen.getByRole('separator')
  fireEvent.pointerDown(separator,{button:0,clientX:450})
  fireEvent.pointerMove(separator,{clientX:900})
  expect(separator.getAttribute('aria-valuenow')).toBe('63')
  expect(parentMove).not.toHaveBeenCalled()
  fireEvent.pointerUp(separator)
  fireEvent.click(screen.getByRole('button',{name:'扩大成果区'}))
  expect(document.querySelector('.is-resource-expanded')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'恢复左右布局'}))
  expect(separator.getAttribute('aria-valuenow')).toBe('63')
  rect.mockRestore();vi.unstubAllGlobals();localStorage.clear()
})

it('lets the keyboard resize and restore the conversation/product split', () => {
  localStorage.clear()
  const view=render(<ThreadWorkspace conversationOnly resourcePanel={<p>真实成果</p>} resourcePanelOpen><p>对话</p></ThreadWorkspace>)
  const separator=screen.getByRole('separator',{name:'调整对话与成果宽度'})
  expect(separator.getAttribute('aria-valuenow')).toBe('67')
  fireEvent.keyDown(separator,{key:'ArrowRight'})
  expect(separator.getAttribute('aria-valuenow')).toBe('69')
  view.unmount()
  render(<ThreadWorkspace conversationOnly resourcePanel={<p>真实成果</p>} resourcePanelOpen><p>对话</p></ThreadWorkspace>)
  expect(screen.getByRole('separator').getAttribute('aria-valuenow')).toBe('69')
  localStorage.clear()
})

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
