import {describe,it,expect} from 'vitest'
import {buildControlGoal,parseControlGoal,controlGoalCommand} from './controlGoals'

export const goalDocument=()=>({schema:'capstone-control-goal/1',workspace:'enterprise',goal_id:'goal_one',revision:3,
  objective_revision:1,objective:'Produce a report',acceptance_criteria:['Review the report'],state:'running',reason:null,
  max_delegations:4,delegations_admitted:1,deadline_at:'2099-01-01T00:00:00Z',acceptance:null,history:[],tasks:[
    {task_id:'stage_1',revision:1,objective:'Prepare draft',delivery_requirements:['Save draft.txt'],required_products:['draft.txt'],
      depends_on:[],agent_id:'capstone',mode:'single',max_attempts:1,state:'running',generation:1,
      delegation:{delegation_id:'delegation_one',binding:{thread_id:'thr_one',work_id:'work_one'}},delivery:null,verification:null}]})

describe('Control Goal contracts',()=>{
  it('builds explicit ordered phases and separate finite budgets',()=>{
    const body=buildControlGoal({objective:'Report',criteria:'Review files',maxDelegations:4,deadline:'2099-01-01T00:00:00Z',
      stages:[{objective:'Draft',files:'draft.txt',mode:'single',maxAttempts:1},
              {objective:'Review',files:'final.md',mode:'goal',maxAttempts:3}]},'create_one')
    expect(body.tasks[1].depends_on).toEqual(['stage_1'])
    expect(body.tasks[1].required_products).toEqual(['final.md'])
    expect(body.max_delegations).toBe(4)
    expect(body.tasks[1].max_attempts).toBe(3)
  })
  it('binds a control to the current Goal revision',()=>{
    const goal=parseControlGoal(goalDocument())
    expect(controlGoalCommand(goal,'pause',{},'pause_one')).toMatchObject({goal_id:'goal_one',expected_revision:3,operation_id:'pause_one'})
  })
  it('rejects boolean revisions and cross-Thread product identities',()=>{
    expect(()=>parseControlGoal({...goalDocument(),revision:true})).toThrow()
    expect(()=>buildControlGoal({objective:'Report',criteria:'Review',maxDelegations:0,deadline:'2099-01-01',stages:[]},'bad')).toThrow()
  })
})
