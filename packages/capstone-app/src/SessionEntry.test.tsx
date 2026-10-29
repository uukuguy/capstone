import {StrictMode} from 'react'
import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import SessionEntry from './SessionEntry'
afterEach(cleanup)
it('waits for an explicit creation when entering a workspace without a thread',async()=>{
  const create=vi.fn().mockResolvedValue(undefined)
  render(<SessionEntry onCreate={create} autoCreate={false}/>)
  expect(create).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button',{name:'新建会话'}))
  await waitFor(()=>expect(create).toHaveBeenCalledExactlyOnceWith({session_type:'enterprise-research'}))
})
it('opens one unified session without type or model selection, including StrictMode',async()=>{
  const create=vi.fn().mockResolvedValue(undefined)
  render(<StrictMode><SessionEntry onCreate={create}/></StrictMode>)
  await waitFor(()=>expect(create).toHaveBeenCalledExactlyOnceWith({session_type:'enterprise-research'}))
  expect(screen.queryByRole('radio')).toBeNull()
  expect(screen.queryByRole('combobox')).toBeNull()
})
it('shows creation failure and permits an explicit retry',async()=>{
  const create=vi.fn().mockRejectedValueOnce(new Error('连接中断，请重试。')).mockResolvedValue(undefined)
  render(<SessionEntry onCreate={create}/>)
  expect((await screen.findByRole('alert')).textContent).toContain('连接中断')
  fireEvent.click(screen.getByRole('button',{name:'重试创建'}))
  await waitFor(()=>expect(create).toHaveBeenCalledTimes(2))
})
