import {expect,it} from 'vitest'
import {missionObjectiveFromInput,parseMission,parseMissionRefs} from './missions'
it('recognizes only the explicit Mission entry and preserves rough intent',()=>{
  expect(missionObjectiveFromInput('/mission 帮我准备研究')).toBe('帮我准备研究')
  expect(missionObjectiveFromInput('讨论 /mission')).toBeNull()
  expect(missionObjectiveFromInput('/missions')).toBeNull()
  expect(missionObjectiveFromInput('/goal 研究')).toBeNull()
})
it('keeps Mission aggregate identity and validates the owning Thread',()=>{
  const row={schema:'capstone-control-mission/1',mission_id:'goal_one',goal_id:'goal_one',workspace:'enterprise',objective:'研究',state:'planning',revision:1,origin:{thread_id:'thr_one'},plan_complete:false}
  expect(parseMission(row,'enterprise','thr_one').missionId).toBe('goal_one')
  expect(()=>parseMission({...row,origin:{thread_id:'thr_other'}},'enterprise','thr_one')).toThrow()
  expect(()=>parseMission({...row,mission_id:'goal_other'},'enterprise','thr_one')).toThrow()
  expect(parseMissionRefs([{mission_id:'goal_one'}])).toEqual([{missionId:'goal_one'}])
})
