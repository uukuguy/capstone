import {describe,it,expect} from 'vitest'
import {parseGoalMode,goalCommand} from './goalMode'
import {parseStoredWorkCommand} from './threadWorkProtocol'

describe('goal mode protocol',()=>{
  it('reads persisted state and rejects invalid budgets',()=>{
    const goal={schema:'capstone-work-goal/1',objective:'Report',objective_revision:1,
      generation:1,state:'paused',reason:'user_pause',max_attempts:3,attempts_admitted:1,
      deadline_at:'2099-01-01T00:00:00Z',last_settled_attempt_id:null}
    expect(parseGoalMode(goal).state).toBe('paused')
    expect(()=>parseGoalMode({...goal,max_attempts:true})).toThrow()
  })
  it('binds controls to the selected Work revision',()=>{
    const command=goalCommand('thr_one','run_one','cmd_one','key_one','work_one',3,'pause_goal',{})
    expect(command.target.expected_revision).toBe(3)
    expect(command.kind).toBe('pause_goal')
    expect(parseStoredWorkCommand(command,'thr_one')).toEqual(command)
  })
})
