import {render,screen,fireEvent} from '@testing-library/react'
import {it,expect,vi} from 'vitest'
import GoalControls from './GoalControls'

it('submits an explicit bounded goal',()=>{
  const submit=vi.fn()
  render(<GoalControls objective="Review report" disabled={false} onControl={submit}/> )
  fireEvent.click(screen.getByRole('button',{name:'启用持续目标'}))
  expect(submit).toHaveBeenCalledWith('start_goal',expect.objectContaining({objective:'Review report',max_attempts:8}))
})

it('shows a paused objective and submits its revision',()=>{
  const submit=vi.fn()
  render(<GoalControls objective="Review report" disabled={false} onControl={submit} goal={{
    schema:'capstone-work-goal/1',objective:'Review report',objective_revision:1,generation:1,
    state:'paused',reason:'user_pause',max_attempts:8,attempts_admitted:1,
    deadline_at:'2099-01-01T00:00:00Z',last_settled_attempt_id:null}}/> )
  expect(screen.getByText(/已暂停/)).toBeTruthy()
  fireEvent.change(screen.getByLabelText('修改目标'),{target:{value:'Review revised report'}})
  fireEvent.click(screen.getByRole('button',{name:'保存目标修改'}))
  expect(submit).toHaveBeenCalledWith('revise_goal_objective',{objective:'Review revised report'})
})
