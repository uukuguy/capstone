/** Application-neutral, explicit whole-goal coverage. No execution or acceptance. */
const check=(ok,message)=>{if(!ok){const error=new Error(message);error.code='task_goal_invalid';throw error;}};
const exact=(value,keys)=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join(',')===[...keys].sort().join(',');
const text=value=>typeof value==='string'&&value.trim().length>0;
const unique=values=>Array.isArray(values)&&new Set(values).size===values.length;
const clone=value=>structuredClone(value);
export const taskRequirementSchema={type:'object',additionalProperties:false,required:['id','description','kind'],properties:{
  id:{type:'string',minLength:1},description:{type:'string',minLength:1},kind:{type:'string',enum:['finding','artifact']}}};
export const taskGoalReviewSchema={type:'object',additionalProperties:false,required:['decision','requirements','summary'],properties:{
  decision:{type:'string',enum:['continue','complete','limited','blocked']},summary:{type:'string',minLength:1},
  requirements:{type:'array',description:'Supply changed coverage for registered requirement IDs. The host retains prior satisfied coverage only while its exact result versions remain current; other omitted requirements stay open. Complete still requires full coverage.',items:{type:'object',additionalProperties:false,required:['id','status','result_refs','explanation'],properties:{
    id:{type:'string',minLength:1},status:{type:'string',enum:['satisfied','open','blocked']},
    result_refs:{type:'array',items:{type:'string',minLength:1}},explanation:{type:'string',minLength:1},
    blocker:{type:'object',additionalProperties:false,required:['kind','explanation'],properties:{
      kind:{type:'string',enum:['missing_input','permission','failed_capability','hard_limit']},explanation:{type:'string',minLength:1}}}}}}}};
export function createTaskGoal(requirements,limits={maxItems:Infinity,maxText:Infinity}){
  check(Array.isArray(requirements)&&requirements.length>0&&requirements.length<=limits.maxItems,'Declare bounded whole-goal requirements before execution');
  check(unique(requirements.map(item=>item.id)),'Whole-goal requirement IDs must be unique');
  for(const item of requirements)check(exact(item,['id','description','kind'])&&text(item.id)&&text(item.description)&&
    item.id.length<=limits.maxText&&item.description.length<=limits.maxText&&['finding','artifact'].includes(item.kind),'Invalid whole-goal requirement');
  return {schema:'capstone-task-goal/1',requirements:clone(requirements),review:null};
}
export function reviewTaskGoal(goal,payload,context){
  check(goal?.schema==='capstone-task-goal/1','A registered whole goal is required');
  check(exact(payload,['decision','requirements','summary'])&&['continue','complete','limited','blocked'].includes(payload.decision)&&text(payload.summary),'Invalid whole-goal review');
  check(Array.isArray(payload.requirements)&&
    unique(payload.requirements.map(item=>item.id))&&payload.requirements.every(item=>goal.requirements.some(required=>required.id===item.id)),
    'Review only registered whole-goal requirements, without duplicate IDs');
  const supplied=new Set(payload.requirements.map(item=>item.id));
  payload={...payload,requirements:[...payload.requirements,...goal.requirements.filter(required=>!supplied.has(required.id)).map(required=>{
    const previous=goal.review?.requirements.find(item=>item.id===required.id);
    const current=previous?.status==='satisfied'&&previous.result_refs.length>0&&previous.result_refs.every(ref=>
      context.results.some(result=>result.result_ref===ref&&['success','limited'].includes(result.phase)));
    return current?clone(previous):{id:required.id,status:'open',result_refs:[],explanation:'This requirement has no current reviewed coverage.'};
  })]};
  for(const item of payload.requirements){
    check(exact(item,Object.hasOwn(item,'blocker')?['id','status','result_refs','explanation','blocker']:['id','status','result_refs','explanation'])&&
      ['satisfied','open','blocked'].includes(item.status)&&unique(item.result_refs)&&item.result_refs.every(text)&&text(item.explanation),'Invalid requirement coverage');
    const results=item.result_refs.map(ref=>context.results.find(result=>result.result_ref===ref));
    check(results.every(result=>result&&['success','limited'].includes(result.phase)),'Coverage needs exact current assessed result refs');
    if(item.status==='satisfied'){
      check(results.length>0&&!item.blocker,'Satisfied requirements need accepted support, not a blocker');
      if(goal.requirements.find(required=>required.id===item.id).kind==='artifact')
        check(results.some(result=>result.kind==='artifact'&&result.artifact_refs.length>0),'Artifact requirements need actual accepted artifact results');
    }else if(item.status==='blocked'){
      check(exact(item.blocker,['kind','explanation'])&&['missing_input','permission','failed_capability','hard_limit'].includes(item.blocker.kind)&&text(item.blocker.explanation),'Blocked requirements need a precise typed blocker');
      check(item.blocker.kind!=='hard_limit'||context.hard_deadline_reached,'A soft performance target or estimate is not a reached hard deadline');
    }else check(!item.blocker,'Open work is not a blocker');
  }
  if(payload.decision==='complete')check(payload.requirements.every(item=>item.status==='satisfied'),'Whole goal is unfinished');
  if(payload.decision==='blocked')check(payload.requirements.some(item=>item.status==='blocked')&&payload.requirements.every(item=>item.status!=='open'),'Continue planning while open requirements remain');
  if(payload.decision==='continue')check(payload.requirements.some(item=>item.status!=='satisfied'),'A fulfilled goal needs a completion decision');
  return {...clone(goal),review:{...clone(payload),review_ref:context.review_ref,basis:context.basis}};
}
export function validateTaskGoalFinish(goal,payload,context){
  const review=goal?.review;
  check(review&&payload.goal_review_ref===review.review_ref,'Finish requires the exact whole-goal review reference');
  check(review.basis===context.basis,'The whole-goal review is stale; assess current results first');
  check(review.decision!=='continue','Whole goal is unfinished; append justified tasks instead of finishing');
  if(review.decision==='blocked'){check(payload.outcome==='failure','A blocked whole goal may close only as failure');return;}
  if(review.decision==='limited'){
    check(payload.outcome==='limited','A limited research turn must report limited delivery');
    check(Array.isArray(payload.limitations)&&payload.limitations.length>0&&payload.limitations.every(text),'Limited delivery needs explicit limitations');
    const retained=new Set(review.requirements.flatMap(item=>item.result_refs));
    check(payload.delivery_result_refs?.some(ref=>retained.has(ref)),'Limited delivery needs an actual retained result');
    return;
  }
  check(payload.outcome!=='failure','Accepted whole-goal completion requires successful or limited delivery');
  for(const required of goal.requirements.filter(item=>item.kind==='artifact')){
    const covered=review.requirements.find(item=>item.id===required.id);
    check(covered.result_refs.some(ref=>payload.delivery_result_refs?.includes(ref)&&context.results.find(result=>result.result_ref===ref)?.artifact_refs.some(artifact=>payload.delivery_product_refs?.includes(artifact))),
      'Delivery must include an accepted artifact for each requested artifact requirement');
  }
}
