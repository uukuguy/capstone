import {expect,it} from 'vitest'
import {missionObjectiveFromInput,parseMission,parseMissionRefs,missionStateLabel} from './missions'
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
it('distinguishes a review boundary from a concluded and verified delivery',()=>{
 const row={schema:'capstone-control-mission/1',mission_id:'goal_one',goal_id:'goal_one',workspace:'enterprise',objective:'研究',state:'delivered',revision:1,origin:{thread_id:'thr_one'},plan_complete:true,plan_revision:2,acceptance_criteria:['Saved'],tasks:[{task_id:'task_one',state:'verified',delivery:{revision:1,answer_ref:'answer_one',products:[]},verification:{delivery_revision:1}}]}
 expect(missionStateLabel(parseMission({...row,plan_concluded:false},'enterprise','thr_one'))).toBe('等待任务结果复盘')
 const typed={plan_revision:2,summary:'Observed saved answer',criteria_verdicts:[{criterion_index:0,status:'met',explanation:'Read the current answer',evidence:[{kind:'answer',task_id:'task_one',answer_ref:'answer_one'}]}]}
 expect(missionStateLabel(parseMission({...row,plan_concluded:true,plan_conclusion:typed},'enterprise','thr_one'))).toBe('成果可用')
 expect(missionStateLabel(parseMission({...row,plan_concluded:true},'enterprise','thr_one'))).toBe('原计划结论待核验')
 expect(missionStateLabel(parseMission({...row,plan_concluded:true,plan_conclusion:typed,tasks:[{state:'delivered'}]},'enterprise','thr_one'))).toBe('仍有未完成事项')
 expect(missionStateLabel(parseMission({...row,reason:'partial_delivery'},'enterprise','thr_one'))).toBe('部分交付')
 expect(missionStateLabel(parseMission({...row,state:'waiting',reason:'acceptance_incomplete'},'enterprise','thr_one'))).toBe('仍有未完成事项')
 expect(missionStateLabel(parseMission({...row,state:'waiting_review'},'enterprise','thr_one'))).toBe('等待任务结果复盘')
 expect(missionStateLabel(parseMission({...row,state:'waiting_review',organizer:{state:'running'}},'enterprise','thr_one'))).toBe('正在复盘')
})

it('projects direct work and both child execution modes on the main Mission',()=>{
 const row={schema:'capstone-control-mission/1',mission_id:'goal_one',goal_id:'goal_one',workspace:'enterprise',
  objective:'研究',state:'running',revision:1,origin:{thread_id:'thr_one'},plan_complete:true,
  tasks:[
   {task_id:'task_direct',objective:'直办',state:'verified',mode:'single',origin_attempt_id:'attempt_one'},
   {task_id:'task_instruction',objective:'记录',state:'running',mode:'single'},
   {task_id:'task_goal',objective:'复核新文件',state:'pending',mode:'goal',revision:2,depends_on:['task_instruction']},
  ]}
 expect(parseMission(row,'enterprise','thr_one').tasks?.map(task=>task.execution)).toEqual(['direct','single','goal'])
 expect(parseMission(row,'enterprise','thr_one').tasks?.[2]?.dependencies).toEqual(['task_instruction'])
 expect(parseMission(row,'enterprise','thr_one').tasks?.[2]).toMatchObject({revision:2,objective:'复核新文件'})
})

it('projects partial criteria only from the current plan revision',()=>{
 const row={schema:'capstone-control-mission/1',mission_id:'goal_one',goal_id:'goal_one',workspace:'enterprise',
  objective:'研究',state:'delivered',reason:'partial_delivery',revision:7,origin:{thread_id:'thr_one'},plan_complete:true,
  plan_revision:2,acceptance_criteria:['保存结果','核对签名'],plan_conclusion:{plan_revision:2,
   criteria_verdicts:[{criterion_index:1,status:'not_met',explanation:'缺少签名'}]}}
 expect(parseMission(row,'enterprise','thr_one').criteria?.[1]).toEqual({label:'核对签名',status:'not_met',explanation:'缺少签名'})
 expect(parseMission({...row,plan_revision:3},'enterprise','thr_one').criteria?.[1]).toEqual({label:'核对签名'})
})

it('links only evidence matching the current verified child delivery',()=>{
 const sha256='a'.repeat(64), artifact_id=`file-${'b'.repeat(16)}-${sha256}`
 const file={schema:'capstone-process-artifact/1',scope:'instruction',thread_id:'thr_child',run_id:'run_one',
  turn_id:'turn_one',attempt_id:'attempt_one',work_id:'work_child',task_snapshot_id:'snapshot_one',goal_revision:1,
  task_id:'native_one',artifact_id,executor_identity_sha256:'c'.repeat(64),source_status:'completed',
  file_name:'result.txt',media_type:'text/plain',sha256,size_bytes:10,
  download_url:`/api/v1/threads/thr_child/attempts/attempt_one/artifacts/${artifact_id}`}
 const task={task_id:'task_one',state:'verified',verification:{delivery_revision:1},
  delivery:{revision:1,products:[file]},delegation:{binding:{thread_id:'thr_child',work_id:'work_child'}}}
 const row={schema:'capstone-control-mission/1',mission_id:'goal_one',goal_id:'goal_one',workspace:'enterprise',
  objective:'研究',state:'delivered',revision:7,origin:{thread_id:'thr_one'},plan_complete:true,plan_revision:2,
  acceptance_criteria:['保存结果'],tasks:[task],plan_conclusion:{plan_revision:2,criteria_verdicts:[
   {criterion_index:0,status:'met',explanation:'已保存',evidence:[{kind:'product',task_id:'task_one',artifact_id,sha256}]}]}}
 expect(parseMission(row,'enterprise','thr_one').criteria?.[0]?.products?.map(item=>item.artifact_id)).toEqual([artifact_id])
 expect(parseMission({...row,tasks:[{...task,verification:{delivery_revision:2}}]},'enterprise','thr_one').criteria?.[0]?.products).toEqual([])
 expect(parseMission({...row,tasks:[{...task,delegation:{binding:{thread_id:'thr_other',work_id:'work_child'}}}]},'enterprise','thr_one').criteria?.[0]?.products).toEqual([])
})
