import {cleanup,render,screen,fireEvent} from '@testing-library/react'
import {afterEach,it,expect,vi} from 'vitest'
import GoalControls from './GoalControls'

afterEach(cleanup)

it('submits an explicit bounded goal',()=>{
  const submit=vi.fn()
  render(<GoalControls objective="Review report" disabled={false} onControl={submit}/> )
  const settings=screen.getByText('执行设置').closest('details')
  expect(settings?.open).toBe(false)
  fireEvent.click(screen.getByRole('button',{name:'开始规划目标'}))
  expect(submit).toHaveBeenCalledWith('start_goal',expect.objectContaining({objective:'Review report',max_attempts:8}))
})

it('shows a paused objective and submits its revision',()=>{
  const submit=vi.fn()
  render(<GoalControls objective="Review report" disabled={false} onControl={submit} goal={{
    schema:'capstone-work-goal/1',objective:'Review report',objective_revision:1,generation:1,
    state:'paused',reason:'user_pause',max_attempts:8,attempts_admitted:1,
    deadline_at:'2099-01-01T00:00:00Z',last_settled_attempt_id:null}}/> )
  expect(screen.getByText(/已暂停/)).toBeTruthy()
  fireEvent.click(screen.getByText('修改或结束目标'))
  fireEvent.change(screen.getByLabelText('修改目标'),{target:{value:'Review revised report'}})
  fireEvent.click(screen.getByRole('button',{name:'保存目标修改'}))
  expect(submit).toHaveBeenCalledWith('revise_goal_objective',{objective:'Review revised report'})
})

it.each(['goal_review_invalid','goal_review_criteria_incomplete'])('offers review and follow-up for %s',(reason)=>{
  const submit=vi.fn()
  render(<GoalControls objective="Review report" disabled={false} onControl={submit} goal={{
    schema:'capstone-work-goal/1',objective:'Review report',objective_revision:1,generation:1,
    state:'paused',reason,max_attempts:8,attempts_admitted:2,
    deadline_at:'2000-01-01T00:00:00Z',last_settled_attempt_id:'attempt_previous'}}/>)
  expect(screen.getByText(/可直接在消息框发送新指令/)).toBeTruthy()
  if(reason==='goal_review_criteria_incomplete')expect(screen.getByText(/逐项核实全部验收条件/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'重新复盘已保存成果'}))
  expect(submit).toHaveBeenCalledWith('resume_goal',{})
})

it('shows the saved plan and allows pause during review',()=>{
  const submit=vi.fn()
  render(<GoalControls objective="Build report" disabled={false} onControl={submit} goal={{
    schema:'capstone-work-goal/1',objective:'Build report',objective_revision:1,generation:1,
    state:'waiting',reason:'goal_review_pending',max_attempts:8,attempts_admitted:1,
    deadline_at:'2099-01-01T00:00:00Z',last_settled_attempt_id:'attempt_first'}}
    plan={{stepIndex:0,criteria:['Verified report'],steps:[
      {instruction:'Check sources',expectedResult:'Source receipt'},
      {instruction:'Write report',expectedResult:'Saved report'}]}}/>)
  expect(screen.getByRole('status').textContent).toContain('正在复盘')
  fireEvent.click(screen.getByText('目标计划 · 第 1/2 步'))
  expect(screen.getByText('Check sources').getAttribute('aria-current')).toBe('step')
  expect(screen.getByText('Verified report')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'暂停目标'}))
  expect(submit).toHaveBeenCalledWith('pause_goal',{})
})
