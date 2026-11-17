import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import InstructionStatus from './InstructionStatus'
afterEach(cleanup)
it('keeps stop separate and exposes only pending withdrawals in durable order',()=>{
  const stop=vi.fn(),withdraw=vi.fn(),locate=vi.fn()
  render(<InstructionStatus active stopping={false} stopped={false} waiting={false} disabled={false} canStop onStop={stop} onWithdraw={withdraw} onLocate={locate} queue={[{id:'ins_one',text:'检查来源',attemptId:'att_one',sequence:1,state:'pending'},{id:'ins_two',text:'已送达',attemptId:'att_one',sequence:2,state:'admitted'}]}/> )
  expect(screen.queryByText('检查来源')).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'待接纳指令 1'}))
  fireEvent.click(screen.getByRole('button',{name:'撤回'}))
  expect(withdraw).toHaveBeenCalledWith('ins_one')
  fireEvent.click(screen.getByRole('button',{name:'查看来源执行'}))
  expect(locate).toHaveBeenCalledWith('att_one')
  fireEvent.click(screen.getByRole('button',{name:'停止生成'}))
  expect(stop).toHaveBeenCalledOnce()
})
it('keeps pending instructions visible after stop without an automatic restart action',()=>{
  render(<InstructionStatus active={false} stopping={false} stopped waiting={false} disabled={false} canStop={false} onStop={vi.fn()} onWithdraw={vi.fn()} onLocate={vi.fn()} queue={[{id:'ins_one',text:'保留指令',attemptId:'att_one',sequence:1,state:'pending'}]}/> )
  fireEvent.click(screen.getByRole('button',{name:'待接纳指令 1'}))
  expect(screen.getByText('保留指令')).toBeTruthy()
  expect(screen.queryByRole('button',{name:'停止生成'})).toBeNull()
})
