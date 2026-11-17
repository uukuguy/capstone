import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react'
import {beforeEach,afterEach,it,expect,vi} from 'vitest'
import ControlGoals from './ControlGoalPanel'
import {parseControlGoal} from './controlGoals'

beforeEach(()=>localStorage.clear())
afterEach(cleanup)
const goal=()=>parseControlGoal({schema:'capstone-control-goal/1',workspace:'enterprise',goal_id:'goal_one',revision:3,
  objective_revision:1,objective:'Produce a report',acceptance_criteria:['Review report'],state:'running',reason:null,
  max_delegations:4,delegations_admitted:1,deadline_at:'2099-01-01T00:00:00Z',acceptance:null,tasks:[
    {task_id:'stage_1',revision:1,objective:'Prepare draft',delivery_requirements:['Save draft.txt'],required_products:['draft.txt'],
      depends_on:[],agent_id:'capstone',mode:'single',max_attempts:1,state:'running',
      delegation:{delegation_id:'delegation_one',binding:{thread_id:'thr_one',work_id:'work_one'}},delivery:null,verification:null}]})
function transport(goals=[goal()]){return {workspaceName:'enterprise',controlGoals:vi.fn().mockResolvedValue({goals,nextCursor:null}),
  controlGoal:vi.fn().mockResolvedValue(goals[0]??goal()),createControlGoal:vi.fn(),controlGoalCommand:vi.fn()}}

it('opens the existing delegated Thread instead of building another chat',async()=>{
  const api=transport(),open=vi.fn()
  render(<ControlGoals transport={api} onOpenThread={open}/> )
  fireEvent.click(screen.getByRole('button',{name:'长期目标'}))
  await screen.findByRole('heading',{name:'Produce a report'})
  fireEvent.click(screen.getByRole('button',{name:'打开阶段 1 会话'}))
  expect(open).toHaveBeenCalledWith('thr_one','work_one')
})

it('retains an uncertain creation request and retries the exact operation',async()=>{
  const api=transport([])
  api.createControlGoal.mockRejectedValueOnce(new Error('连接中断')).mockResolvedValue(goal())
  render(<ControlGoals transport={api} onOpenThread={()=>{}}/> )
  fireEvent.click(screen.getByRole('button',{name:'长期目标'}))
  fireEvent.click(await screen.findByRole('button',{name:'新建长期目标'}))
  fireEvent.change(screen.getByLabelText('长期目标内容'),{target:{value:'Produce report'}})
  fireEvent.change(screen.getByLabelText('最终验收条件'),{target:{value:'Review final file'}})
  fireEvent.change(screen.getByLabelText('阶段 1 目标'),{target:{value:'Save a draft'}})
  fireEvent.change(screen.getByLabelText('阶段 2 目标'),{target:{value:'Read draft and save report'}})
  fireEvent.click(screen.getByRole('button',{name:'创建并开始'}))
  await screen.findByText('连接中断')
  fireEvent.click(screen.getByRole('button',{name:'重试原请求'}))
  await waitFor(()=>expect(api.createControlGoal).toHaveBeenCalledTimes(2))
  expect(api.createControlGoal.mock.calls[1][0]).toEqual(api.createControlGoal.mock.calls[0][0])
})

it('restores a pending operation after remount without creating a new identity',async()=>{
  const body={schema:'capstone-control-command/1',operation_id:'pause_original',goal_id:'goal_one',expected_revision:3,kind:'pause',payload:{}}
  localStorage.setItem('capstone.control.enterprise.pending',JSON.stringify({kind:'command',body}))
  const api=transport()
  api.controlGoalCommand.mockResolvedValue({goal:goal()})
  render(<ControlGoals transport={api} onOpenThread={()=>{}}/> )
  fireEvent.click(screen.getByRole('button',{name:'长期目标'}))
  fireEvent.click(await screen.findByRole('button',{name:'重试原请求'}))
  await waitFor(()=>expect(api.controlGoalCommand).toHaveBeenCalledWith(body))
})

it('recovers an invalid local draft without changing server Goal state',async()=>{
  localStorage.setItem('capstone.control.enterprise.draft',JSON.stringify({stages:null}))
  const api=transport([])
  render(<ControlGoals transport={api} onOpenThread={()=>{}}/> )
  fireEvent.click(screen.getByRole('button',{name:'长期目标'}))
  fireEvent.click(await screen.findByRole('button',{name:'新建长期目标'}))
  expect(screen.getByLabelText('阶段 1 目标')).toBeTruthy()
  expect(api.createControlGoal).not.toHaveBeenCalled()
})

it('ignores an old goal read that finishes after selecting another goal',async()=>{
 const first=goal(),second={...goal(),goal_id:'goal_two',objective:'Second report'}
 let finish!:(value:ReturnType<typeof goal>)=>void
 const api=transport([first,second])
 api.controlGoal.mockImplementation((id:string)=>id==='goal_one'?new Promise(resolve=>{finish=resolve}):Promise.resolve(second))
 render(<ControlGoals transport={api} onOpenThread={()=>{}}/>)
 fireEvent.click(screen.getByRole('button',{name:'长期目标'}))
 await waitFor(()=>expect(api.controlGoal).toHaveBeenCalledWith('goal_one'))
 fireEvent.change(screen.getByLabelText('选择长期目标'),{target:{value:'goal_two'}})
 await screen.findByRole('heading',{name:'Second report'})
 finish(first)
 await waitFor(()=>expect(api.controlGoal).toHaveBeenCalledWith('goal_two'))
 await new Promise(resolve=>setTimeout(resolve,0))
 expect(screen.queryByRole('heading',{name:'Produce a report'})).toBeNull()
 expect(screen.getByRole('heading',{name:'Second report'})).toBeTruthy()
})
