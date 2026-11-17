import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import ControlWorkspaceViews from './ControlWorkspaceViews'
import type {ControlGoal} from './controlGoals'
import type {ControlEventPage} from './controlEvents'

afterEach(cleanup)
const goal:ControlGoal={schema:'capstone-control-goal/1',workspace:'enterprise',goal_id:'goal_one',revision:4,objective_revision:1,
 objective:'报告',state:'pausing',reason:'user_pause',acceptance:null,acceptance_criteria:['核验'],max_delegations:8,delegations_admitted:1,
 deadline_at:'2099-01-01T00:00:00Z',tasks:[{task_id:'t1',revision:1,objective:'任务一',state:'revoke_requested',mode:'single',max_attempts:1,
  delivery_requirements:['报告'],required_products:[],depends_on:[],delegation:{delegation_id:'d1',binding:{thread_id:'thr_current',work_id:'work_current'}},
  delivery:null,verification:null}]}
function page():ControlEventPage{return {schema:'capstone-control-events/1',workspace:'enterprise',goal_id:'goal_one',
 after_sequence:0,next_sequence:1,through_sequence:1,has_more:false,history_complete:false,first_recorded_goal_revision:3,
 events:[{schema:'capstone-control-event/1',source:'capstone-control',workspace:'enterprise',goal_id:'goal_one',event_id:'e1',sequence:1,
 kind:'command.pause',recorded_at:'2026-11-17T12:00:00Z',before:{revision:2,objective_revision:1,state:'running',reason:null},
 after:{revision:3,objective_revision:1,state:'pausing',reason:'user_pause'},history_complete:false,missing_goal_revisions:{from:1,through:2},
 task_changes:[{task_id:'t1',after:null,before:{task_id:'t1',task_revision:1,objective_revision:1,generation:1,state:'running',
 delegation_id:'old_d',binding:{thread_id:'thr_old',work_id:'work_old'},requested_control:null,control_revision:0,delivery_revision:null}}]}]}}
function props(){return {goal,disabled:false,onOpenThread:vi.fn(),onVerify:vi.fn(),readEvents:vi.fn().mockResolvedValue(page())}}
it('loads on observation entry and returns to the same source event without remounting the board',async()=>{
 const p=props();render(<ControlWorkspaceViews {...p}/>)
 const card=screen.getByRole('button',{name:'查看任务：任务一'});fireEvent.click(card)
 expect(p.readEvents).not.toHaveBeenCalled()
 fireEvent.click(screen.getByRole('tab',{name:'运行观察'}))
 const source=await screen.findByRole('button',{name:'诊断控制事件 #1'})
 const lane=screen.getByLabelText('运行泳道');lane.scrollTop=80
 fireEvent.click(source)
 expect(screen.getByRole('tab',{name:'研发诊断'}).getAttribute('aria-selected')).toBe('true')
 expect(screen.getByText('e1')).toBeTruthy()
 fireEvent.click(screen.getByRole('button',{name:'打开记录中的执行会话'}))
 expect(p.onOpenThread).toHaveBeenCalledWith('thr_old','work_old')
 fireEvent.click(screen.getByRole('button',{name:'返回运行观察'}))
 await waitFor(()=>expect(document.activeElement).toBe(source))
 expect(screen.getByLabelText('运行泳道').scrollTop).toBe(80)
 fireEvent.click(screen.getByRole('tab',{name:'任务执行'}))
 expect(screen.getByRole('button',{name:'查看任务：任务一'})).toBe(card)
 expect(card.getAttribute('aria-pressed')).toBe('true')
})
it('labels incomplete history and keeps requested stop distinct from acknowledgement',async()=>{
 render(<ControlWorkspaceViews {...props()}/>)
 fireEvent.click(screen.getByRole('tab',{name:'运行观察'}))
 await screen.findByRole('button',{name:'诊断控制事件 #1'})
 expect(screen.getByText(/历史不完整/)).toBeTruthy()
 expect(within(screen.getByLabelText('运行泳道')).getByText('停止请求待确认')).toBeTruthy()
 expect(screen.getByText(/当前状态与事件读取上界分别显示/)).toBeTruthy()
})
it('pins pagination to the first response boundary',async()=>{
 const p=props(),first={...page(),through_sequence:2,has_more:true}
 p.readEvents.mockResolvedValueOnce(first).mockResolvedValueOnce({...page(),after_sequence:1,next_sequence:2,through_sequence:2,
 events:[{...page().events[0],event_id:'e2',sequence:2}]})
 render(<ControlWorkspaceViews {...p}/>)
 fireEvent.click(screen.getByRole('tab',{name:'运行观察'}))
 fireEvent.click(await screen.findByRole('button',{name:'载入更多事件'}))
 await waitFor(()=>expect(p.readEvents).toHaveBeenCalledWith('goal_one',1,2))
 expect(await screen.findByRole('button',{name:'诊断控制事件 #2'})).toBeTruthy()
})
it('does not show a late response after switching Goal',async()=>{
 let resolve!:(p:ControlEventPage)=>void
 const p=props();p.readEvents.mockImplementation(()=>new Promise(r=>{resolve=r}))
 const view=render(<ControlWorkspaceViews {...p}/>)
 fireEvent.click(screen.getByRole('tab',{name:'运行观察'}))
 await waitFor(()=>expect(p.readEvents).toHaveBeenCalled())
 view.rerender(<ControlWorkspaceViews {...p} goal={{...goal,goal_id:'goal_two'}}/>)
 resolve(page())
 await waitFor(()=>expect(screen.queryByRole('button',{name:'诊断控制事件 #1'})).toBeNull())
 expect(screen.getByRole('tab',{name:'任务执行'}).getAttribute('aria-selected')).toBe('true')
})
it('keeps the selected historical record when current state changes and read refresh fails',async()=>{
 const p=props();const view=render(<ControlWorkspaceViews {...p}/>)
 fireEvent.click(screen.getByRole('tab',{name:'运行观察'}))
 fireEvent.click(await screen.findByRole('button',{name:'诊断控制事件 #1'}))
 view.rerender(<ControlWorkspaceViews {...p} goal={{...goal,revision:10,state:'accepted'}}/>)
 expect(screen.getByText('e1')).toBeTruthy()
 expect(screen.getByText('2 → 3')).toBeTruthy()
 p.readEvents.mockRejectedValueOnce(new Error('连接中断'))
 fireEvent.click(screen.getByRole('button',{name:'刷新事件'}))
 expect(await screen.findByRole('alert')).toHaveProperty('textContent',expect.stringContaining('保留上次成功读取'))
 expect(screen.getByText('e1')).toBeTruthy()
})
it('preserves the old execution requirement version while Goal revision is changing',async()=>{
 const p=props();p.goal={...goal,objective_revision:2,state:'revising',tasks:[{...goal.tasks[0],
  delegation:{...goal.tasks[0].delegation!,goal_revision:1,generation:1,agent_id:'capstone'}}]}
 render(<ControlWorkspaceViews {...p}/>)
 fireEvent.click(screen.getByRole('tab',{name:'运行观察'}))
 expect(await screen.findByText('执行要求版本 1 · 第 1 次委托')).toBeTruthy()
})
