import {render,screen,fireEvent,cleanup,within} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import ControlTaskBoard,{taskColumn,taskIdentity} from './ControlTaskBoard'
import type {ControlGoal,ControlTask} from './controlGoals'

afterEach(cleanup)
function task(id:string,state:string):ControlTask{return {task_id:id,revision:1,objective:id,state,mode:'single',max_attempts:1,
  delivery_requirements:['Save result'],required_products:[],depends_on:[],delegation:null,delivery:null,verification:null}}
function goal(tasks:ControlTask[]):ControlGoal{return {schema:'capstone-control-goal/1',workspace:'enterprise',goal_id:'goal_test',
  revision:1,objective_revision:1,objective:'Report',acceptance_criteria:['Review'],max_delegations:8,delegations_admitted:1,
  deadline_at:'2099-01-01T00:00:00Z',state:'running',reason:null,acceptance:null,tasks}}
it('maps every published task state without treating stopped or failed work as success',()=>{
  const cases:Record<string,string>={pending:'pending',dispatching:'active',running:'active',waiting:'active',paused:'active',
    resume_requested:'active',revoke_requested:'active',blocked:'active',failed:'active',delivered:'review',verified:'done',cancelled:'closed'}
  for(const [state,column] of Object.entries(cases))expect(taskColumn(state)).toBe(column)
  expect(taskColumn('future_state')).toBe('unknown')
})
it('keeps card DOM, selection and focus during same-task state refresh',()=>{
 const first=task('first','running'),second=task('second','pending'),g=goal([first,second])
 const props={goal:g,disabled:false,onOpenThread:vi.fn(),onVerify:vi.fn()}
 const view=render(<ControlTaskBoard {...props}/>)
 const card=screen.getByRole('button',{name:'查看任务：first'})
 card.focus();fireEvent.click(card)
 view.rerender(<ControlTaskBoard {...props} goal={{...g,revision:2,tasks:[{...first,observation:{sequence:1,state:'running',summary:'Still working'}},second]}}/>)
 expect(screen.getByRole('button',{name:'查看任务：first'})).toBe(card)
 expect(document.activeElement).toBe(card)
 expect(card.getAttribute('aria-pressed')).toBe('true')
})
it('uses exact bound session and delivery revision, with cancelled work outside completed',()=>{
 const first={...task('first','delivered'),delegation:{delegation_id:'d1',binding:{thread_id:'thr_one',work_id:'work_one'}},
   delivery:{revision:7,answer_ref:'answer_1',products:[]}}
 const open=vi.fn(),verify=vi.fn()
 render(<ControlTaskBoard goal={goal([first,task('second','cancelled')])} disabled={false} onOpenThread={open} onVerify={verify}/>)
 fireEvent.click(screen.getByRole('button',{name:'查看任务：first'}))
 fireEvent.click(screen.getByRole('button',{name:'打开阶段 1 会话'}))
 expect(open).toHaveBeenCalledWith('thr_one','work_one')
 fireEvent.click(screen.getByRole('button',{name:'确认阶段交付'}))
 expect(verify).toHaveBeenCalledWith('first',7)
 expect(within(screen.getByRole('region',{name:'已完成'})).queryByText('second')).toBeNull()
 expect(within(screen.getByRole('region',{name:'已终止'})).getByRole('button',{name:'查看任务：second'})).toBeTruthy()
})
it('isolates selection identity across objective and task revisions',()=>{
 const t=task('first','running'),g=goal([t])
 expect(taskIdentity(g,t)).not.toBe(taskIdentity({...g,objective_revision:2},t))
 expect(taskIdentity(g,t)).not.toBe(taskIdentity(g,{...t,revision:2}))
 expect(taskIdentity(g,t)).not.toBe(taskIdentity({...g,workspace:'other'},t))
})
