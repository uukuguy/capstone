import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import CapstoneAssistantThread from './CapstoneAssistantThread'
afterEach(()=>{cleanup();sessionStorage.clear()})
it('defaults DR off, removes the skill entry and sends an explicit per-instruction choice',async()=>{
  const onSend=vi.fn(async()=>{})
  render(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={onSend} onCancel={async()=>{}}/>)
  expect(screen.queryByRole('button',{name:'选择技能'})).toBeNull()
  const toggle=screen.getByRole('button',{name:'深度思考'})
  expect(toggle.getAttribute('aria-pressed')).toBe('false')
  fireEvent.click(toggle)
  expect(toggle.getAttribute('aria-pressed')).toBe('true')
  fireEvent.change(screen.getByRole('textbox',{name:'Thread 指令'}),{target:{value:'分析迎峰度夏'}})
  fireEvent.click(screen.getByRole('button',{name:'发送指令'}))
  await waitFor(()=>expect(onSend).toHaveBeenCalledWith('automatic','分析迎峰度夏',expect.objectContaining({deep_research:true})))
  await waitFor(()=>expect(toggle.getAttribute('aria-pressed')).toBe('false'))
})
