import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react'
import {beforeEach,afterEach,it,expect,vi} from 'vitest'
import ControlGoals from './ControlGoalPanel'
import {parseControlGoal,buildControlGoal} from './controlGoals'

beforeEach(()=>localStorage.clear())
afterEach(cleanup)
const goal=()=>parseControlGoal({schema:'capstone-control-goal/1',workspace:'enterprise',goal_id:'goal_one',revision:3,
  objective_revision:1,objective:'Produce a report',acceptance_criteria:['Review report'],state:'running',reason:null,
  max_delegations:4,delegations_admitted:1,deadline_at:'2099-01-01T00:00:00Z',acceptance:null,tasks:[
    {task_id:'stage_1',revision:1,objective:'Prepare draft',delivery_requirements:['Save draft.txt'],required_products:['draft.txt'],
      depends_on:[],agent_id:'capstone',mode:'single',max_attempts:1,state:'running',
      delegation:{delegation_id:'delegation_one',binding:{thread_id:'thr_one',work_id:'work_one'}},delivery:null,verification:null}]})
function transport(goals=[goal()]){return {workspaceName:'enterprise',controlGoals:vi.fn().mockResolvedValue({goals,nextCursor:null}),
  controlGoal:vi.fn().mockResolvedValue(goals[0]??goal()),createControlGoal:vi.fn(),controlGoalCommand:vi.fn(),controlEvents:vi.fn()}}

it('keeps a planning Mission visible alongside legacy Goals and directs changes to its source conversation',async()=>{
  const legacy=goal(),mission=parseControlGoal({...legacy,application_kind:'mission',mission_id:'goal_mission',goal_id:'goal_mission',objective:'Rough intent',origin:{thread_id:'thr_origin'},plan_revision:1,plan_complete:false,state:'planning',tasks:[]})
  const api=transport([mission,legacy]);api.controlGoal.mockImplementation(async(id:string)=>id===legacy.goal_id?legacy:mission)
  render(<ControlGoals transport={api} onOpenThread={vi.fn()}/>)
  fireEvent.click(screen.getByRole('button',{name:'任务执行'}))
  await screen.findByRole('heading',{name:'Rough intent'})
  expect(screen.getByRole('status').textContent).toContain('尚无执行任务')
  expect(screen.getByRole('button',{name:'返回 Mission 来源会话'})).toBeTruthy()
  expect(screen.queryByRole('button',{name:'修改目标与阶段'})).toBeNull()
  fireEvent.change(screen.getByRole('combobox',{name:'选择长期目标'}),{target:{value:'goal_one'}})
  await screen.findByRole('button',{name:'打开阶段 1 会话'})
  expect(screen.getByRole('button',{name:'修改目标与阶段'})).toBeTruthy()
})
it('shows verified Mission results as available without requiring acceptance',async()=>{
  const legacy=goal(),base={...legacy,application_kind:'mission',mission_id:'goal_review',goal_id:'goal_review',origin:{thread_id:'thr_origin'},plan_revision:2,plan_complete:true,state:'delivered',tasks:legacy.tasks.map(task=>({...task,state:'verified',delivery:{revision:1,answer_ref:'answer_one',products:[]},verification:{delivery_revision:1}}))}
  const pending=parseControlGoal({...base,plan_concluded:true,plan_conclusion:{plan_revision:2,summary:'Old opaque done'}}),concluded=parseControlGoal({...base,revision:base.revision+1,plan_concluded:true,plan_conclusion:{plan_revision:2,summary:'Inspected current answer',criteria_verdicts:[{criterion_index:0,status:'met',explanation:'Inspected the saved answer',evidence:[{kind:'answer',task_id:'stage_1',answer_ref:'answer_one'}]}]}})
  const api=transport([pending]);render(<ControlGoals transport={api} onOpenThread={vi.fn()}/>)
  fireEvent.click(screen.getByRole('button',{name:'任务执行'}))
  await screen.findByRole('heading',{name:'Produce a report'})
  expect(screen.queryByRole('button',{name:'接受当前成果版本'})).toBeNull()
  api.controlGoal.mockResolvedValue(concluded)
  fireEvent.click(screen.getByRole('button',{name:'刷新状态'}))
  await screen.findByText('成果可用')
  expect(screen.queryByRole('button',{name:'接受当前成果版本'})).toBeNull()
  expect(api.controlGoalCommand).not.toHaveBeenCalled()
})

it('opens the existing delegated Thread instead of building another chat',async()=>{
  const api=transport(),open=vi.fn()
  render(<ControlGoals transport={api} onOpenThread={open}/> )
  fireEvent.click(screen.getByRole('button',{name:'任务执行'}))
  await screen.findByRole('heading',{name:'Produce a report'})
  fireEvent.click(screen.getByRole('button',{name:'打开阶段 1 会话'}))
  expect(open).toHaveBeenCalledWith('thr_one','work_one')
})

it('shows a delivered goal without a final acceptance action', async () => {
  const api = transport([{...goal(), state: 'delivered'}])
  render(<ControlGoals transport={api} onOpenThread={vi.fn()}/>)
  fireEvent.click(screen.getByRole('button', {name: '任务执行'}))
  await screen.findByText(/成果可用 · 目标版本/)
  expect(screen.queryByRole('button', {name: '接受当前成果版本'})).toBeNull()
  expect(api.controlGoalCommand).not.toHaveBeenCalled()
})

it('directs new creation to the conversation while preserving an existing pending legacy operation',async()=>{
  const body=buildControlGoal({objective:'Produce report',criteria:'Review final file',maxDelegations:4,deadline:'2099-01-01T00:00:00Z',stages:[{objective:'Save a draft',files:'draft.md',mode:'single',maxAttempts:1}]},'create_original')
  localStorage.setItem('capstone.control.enterprise.pending',JSON.stringify({kind:'create',body}))
  const api=transport([])
  api.createControlGoal.mockRejectedValueOnce(new Error('连接中断')).mockResolvedValue(goal())
  render(<ControlGoals transport={api} onOpenThread={()=>{}}/> )
  fireEvent.click(screen.getByRole('button',{name:'任务执行'}))
  expect(screen.queryByRole('button',{name:'新建长期目标'})).toBeNull()
  expect(screen.getByText(/主会话输入 \/mission/)).toBeTruthy()
  fireEvent.click(await screen.findByRole('button',{name:'重试原请求'}))
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
  fireEvent.click(screen.getByRole('button',{name:'任务执行'}))
  fireEvent.click(await screen.findByRole('button',{name:'重试原请求'}))
  await waitFor(()=>expect(api.controlGoalCommand).toHaveBeenCalledWith(body))
})

it('recovers an invalid local draft without changing server Goal state',async()=>{
  localStorage.setItem('capstone.control.enterprise.draft',JSON.stringify({stages:null}))
  const api=transport()
  render(<ControlGoals transport={api} onOpenThread={()=>{}}/> )
  fireEvent.click(screen.getByRole('button',{name:'任务执行'}))
  fireEvent.click(await screen.findByRole('button',{name:'修改目标与阶段'}))
  expect((screen.getByLabelText('阶段 1 目标') as HTMLTextAreaElement).value).toBe('Prepare draft')
  expect(api.createControlGoal).not.toHaveBeenCalled()
})

it('ignores an old goal read that finishes after selecting another goal',async()=>{
 const first=goal(),second={...goal(),goal_id:'goal_two',objective:'Second report'}
 let finish!:(value:ReturnType<typeof goal>)=>void
 const api=transport([first,second])
 api.controlGoal.mockImplementation((id:string)=>id==='goal_one'?new Promise(resolve=>{finish=resolve}):Promise.resolve(second))
 render(<ControlGoals transport={api} onOpenThread={()=>{}}/>)
 fireEvent.click(screen.getByRole('button',{name:'任务执行'}))
 await waitFor(()=>expect(api.controlGoal).toHaveBeenCalledWith('goal_one'))
 fireEvent.change(screen.getByLabelText('选择长期目标'),{target:{value:'goal_two'}})
 await screen.findByRole('heading',{name:'Second report'})
 finish(first)
 await waitFor(()=>expect(api.controlGoal).toHaveBeenCalledWith('goal_two'))
 await new Promise(resolve=>setTimeout(resolve,0))
 expect(screen.queryByRole('heading',{name:'Produce a report'})).toBeNull()
 expect(screen.getByRole('heading',{name:'Second report'})).toBeTruthy()
})
