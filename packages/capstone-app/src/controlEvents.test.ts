import {expect,it} from 'vitest'
import {parseControlEvents} from './controlEvents'

export function eventFixture(sequence=1){
 return {schema:'capstone-control-event/1',source:'capstone-control',workspace:'enterprise',goal_id:'goal_one',
  event_id:'event_'+sequence,sequence,kind:'command.pause',recorded_at:'2026-11-17T12:00:00+00:00',
  before:{revision:sequence,objective_revision:1,state:'running',reason:null},
  after:{revision:sequence+1,objective_revision:1,state:'pausing',reason:'user_pause'},
  history_complete:true,missing_goal_revisions:null,task_changes:[{task_id:'stage_1',
   before:{task_id:'stage_1',task_revision:1,objective_revision:1,generation:1,state:'running',delegation_id:'d1',
    binding:{thread_id:'thr_old',work_id:'work_old'},requested_control:null,control_revision:0,delivery_revision:null},
   after:{task_id:'stage_1',task_revision:1,objective_revision:1,generation:1,state:'revoke_requested',delegation_id:'d1',
    binding:{thread_id:'thr_old',work_id:'work_old'},requested_control:'pause',control_revision:1,delivery_revision:null}}]}
}
export function pageFixture(){
 return {schema:'capstone-control-events/1',workspace:'enterprise',goal_id:'goal_one',events:[eventFixture()],
  after_sequence:0,through_sequence:1,next_sequence:1,has_more:false,history_complete:true,first_recorded_goal_revision:2}
}
it('validates a bounded source prefix and preserves exact recorded bindings',()=>{
 const result=parseControlEvents(pageFixture(),'enterprise','goal_one',0)
 expect(result.events[0].task_changes[0].before?.binding?.work_id).toBe('work_old')
})
it('rejects another workspace, goal and unexpected pagination boundaries',()=>{
 for(const patch of [{workspace:'other'},{goal_id:'other'},{after_sequence:1},{next_sequence:9},{through_sequence:0},{has_more:true}]){
  expect(()=>parseControlEvents({...pageFixture(),...patch},'enterprise','goal_one',0)).toThrow()
 }
 expect(()=>parseControlEvents(pageFixture(),'enterprise','goal_one',0,2)).toThrow()
})
it('rejects reordered, duplicated or cross-goal events and inconsistent task identity',()=>{
 for(const events of [[eventFixture(),eventFixture()],[eventFixture(2),eventFixture(1)],
  [{...eventFixture(),goal_id:'other'}],[{...eventFixture(),source:'agent'}],
  [{...eventFixture(),task_changes:[{...eventFixture().task_changes[0],task_id:'wrong'}]}]]){
  expect(()=>parseControlEvents({...pageFixture(),events},'enterprise','goal_one',0)).toThrow()
 }
})
it('allows honest empty legacy coverage',()=>{
 const result=parseControlEvents({...pageFixture(),events:[],through_sequence:0,next_sequence:0,
  history_complete:false,first_recorded_goal_revision:null},'enterprise','goal_one',0)
 expect(result.history_complete).toBe(false)
})
