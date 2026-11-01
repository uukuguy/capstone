import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import CapstoneAssistantThread from './CapstoneAssistantThread'
import {MessageNotSentError} from '@assistant-ui/react'
afterEach(()=>{cleanup();sessionStorage.clear()})
it('keeps deep research disabled and submits ordinary instructions',async()=>{
  const onSend=vi.fn(async()=>{})
  render(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={onSend} onCancel={async()=>{}}/>)
  expect(screen.queryByRole('button',{name:'选择技能'})).toBeNull()
  expect(screen.queryByRole('button',{name:'本轮上下文'})).toBeNull()
  const toggle=screen.getByRole('button',{name:'深度研究'})
  expect(toggle.getAttribute('aria-pressed')).toBe('false')
  fireEvent.click(toggle)
  expect((toggle as HTMLButtonElement).disabled).toBe(true)
  fireEvent.change(screen.getByRole('textbox',{name:'Thread 指令'}),{target:{value:'分析迎峰度夏'}})
  fireEvent.click(screen.getByRole('button',{name:'发送指令'}))
  await waitFor(()=>expect(onSend).toHaveBeenCalledWith('automatic','分析迎峰度夏',expect.objectContaining({deep_research:false})))
  await waitFor(()=>expect(toggle.getAttribute('aria-pressed')).toBe('false'))
  fireEvent.click(toggle)
  fireEvent.click(toggle)
  expect(toggle.getAttribute('aria-pressed')).toBe('false')
  fireEvent.change(screen.getByRole('textbox',{name:'Thread 指令'}),{target:{value:'第二条普通指令'}})
  fireEvent.click(screen.getByRole('button',{name:'发送指令'}))
  await waitFor(()=>expect(onSend).toHaveBeenLastCalledWith('automatic','第二条普通指令',expect.objectContaining({deep_research:false})))
})
it('restores unconfirmed text without enabling deep research',async()=>{
  const onSend=vi.fn(async()=>{throw new MessageNotSentError('receipt unknown')})
  const props={events:[],disabled:false,isRunning:false,activity:[],onSend,onCancel:async()=>{},storageKey:'dr-uncertain'}
  const view=render(<CapstoneAssistantThread {...props}/>)
  fireEvent.click(screen.getByRole('button',{name:'深度研究'}))
  fireEvent.change(screen.getByRole('textbox',{name:'Thread 指令'}),{target:{value:'保留原选择'}})
  fireEvent.click(screen.getByRole('button',{name:'发送指令'}))
  await waitFor(()=>expect(onSend).toHaveBeenCalled())
  view.unmount()
  render(<CapstoneAssistantThread {...props}/>)
  expect(screen.getByRole('button',{name:'深度研究'}).getAttribute('aria-pressed')).toBe('false')
  expect((screen.getByRole('textbox',{name:'Thread 指令'}) as HTMLTextAreaElement).value).toBe('保留原选择')
})
