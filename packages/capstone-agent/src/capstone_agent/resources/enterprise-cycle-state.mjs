/** Pure enterprise objective transitions. No model, storage, timers or retry.
 * Context receipts/products/sources MUST already be admitted by the host.
 * The caller commits the returned state atomically through the existing CAS
 * adapter before exposing pending_action. The adapter also owns request replay.
 */
import {createHash} from 'node:crypto';
import {validateCycleOperation,requireCycle,EnterpriseCycleError} from './enterprise-cycle-contract.mjs';

const SCHEMA='capstone-enterprise-cycle/1';
const phases=new Set(['executing','assessing','done','limited','blocked']);
const statuses=new Set(['pending','running','executed','met','partial','failed','limited','superseded']);
const nonempty=value=>typeof value==='string'&&value.trim().length>0;
// Only bounded public record IDs are echoed. Arbitrary field content may be
// business text or private data, and must not become an error-message payload.
const publicId=value=>/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(value)?JSON.stringify(value):'[invalid objective ID]';
const unique=items=>[...new Set(items)];
const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?
  Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
const same=(a,b)=>JSON.stringify(canonical(a))===JSON.stringify(canonical(b));
function copy(value) {
  const visit=item=>{
    if(item===null||typeof item==='string'||typeof item==='boolean'||typeof item==='number'&&Number.isFinite(item))return;
    requireCycle(item&&typeof item==='object'&&(Array.isArray(item)||Object.getPrototypeOf(item)===Object.prototype),'Expected plain finite JSON');
    for(const child of Object.values(item))visit(child);
  };
  visit(value);return structuredClone(value);
}
function owner(value) {
  requireCycle(value&&Object.keys(value).sort().join(',')==='goal_revision,research_id,thread_id,work_id'&&
    ['thread_id','work_id','research_id'].every(key=>nonempty(value[key]))&&Number.isSafeInteger(value.goal_revision)&&value.goal_revision>0,'Invalid cycle owner');
  return {thread_id:value.thread_id,work_id:value.work_id,research_id:value.research_id,goal_revision:value.goal_revision};
}
function capacity(dimension,actual,limit) {
  if(actual>limit) {
    const error=new EnterpriseCycleError('research_capacity_exceeded',`${dimension} exceeds configured capacity`);
    error.capacity={dimension,actual,limit,unit:dimension.endsWith('_bytes')?'bytes':'items'};throw error;
  }
}
function checkedLimits(options) {
  requireCycle(options&&['maxRounds','maxFindings','maxQuestions','snapshotBytes'].every(key=>Number.isSafeInteger(options[key])&&options[key]>0),'Explicit research capacities are required');
  return options;
}
function checkCapacity(state,limits) {
  capacity('research_findings',state.findings.length,limits.maxFindings);
  capacity('research_questions',state.objectives.reduce((sum,item)=>sum+item.questions.length,0),limits.maxQuestions);
  capacity('research_objectives',state.objectives.length,limits.maxQuestions);
  capacity('research_snapshot_bytes',Buffer.byteLength(JSON.stringify(state)),limits.snapshotBytes);
}
function validateGraph(objectives) {
  const ids=new Map();
  for(const item of objectives) {
    requireCycle(!ids.has(item.id),`Objective ${publicId(item.id)}: duplicate id; choose a unique objective ID`);ids.set(item.id,item);
    requireCycle(item.questions.length>0&&item.expected_outputs.length>0,'Objective needs questions and expected outputs');
    requireCycle(unique(item.depends_on).length===item.depends_on.length&&unique(item.checks).length===item.checks.length&&unique(item.resolves).length===item.resolves.length,'Duplicate dependencies or checks');
    requireCycle(!item.depends_on.some(id=>item.resolves.includes(id)),'A repair cannot require its unresolved target to be complete');
    requireCycle(item.mode!=='synthesis'||item.input_refs.length>0,'Synthesis requires admitted inputs');
  }
  for(const item of objectives)for(const field of ['depends_on','resolves'])for(const target of item[field])
    requireCycle(ids.has(target),`Objective ${publicId(item.id)}.${field}: unknown objective ID ${publicId(target)}. Use exact declared objective.id values, not questions, source refs or requirements; use [] for none.`);
  const edges=new Map(objectives.map(item=>[item.id,[...item.depends_on,...(item.supersession?.replacement_ids??[])]]));
  // An old requirement is satisfied by its repair/replacement; this direction
  // must match satisfied(), including mixed dependency/replanning cycles.
  for(const item of objectives)for(const target of item.resolves)edges.get(target).push(item.id);
  for(const [id,targets] of edges)for(const target of targets)requireCycle(ids.has(target),`Objective ${publicId(id)}: unknown replacement ID ${publicId(target)}`);
  const seen=new Set(),active=new Set();
  const walk=id=>{
    requireCycle(!active.has(id),`Objective ${publicId(id)}: cyclic depends_on/resolves graph; remove the cycle without removing required evidence`);
    if(seen.has(id))return;
    active.add(id);for(const dep of edges.get(id))walk(dep);active.delete(id);seen.add(id);
  };
  for(const id of ids.keys())walk(id);
}
function action(state,kind,objective) {
  const identity=JSON.stringify([state.owner,state.attempt_id,state.round,objective.id,kind]);
  return {id:'cycle-'+createHash('sha256').update(identity).digest('hex'),kind,objective_id:objective.id,
    attempt_id:state.attempt_id,round:state.round,purpose:objective.purpose,
    questions:[...objective.questions],derived_from:[...(objective.derived_from??[])],
    expected_outputs:[...objective.expected_outputs],checks:[...objective.checks],
    ...(objective.subtasks?{subtasks:structuredClone(objective.subtasks)}:{})};
}
function readyObjectives(state) {
  const ids=unique([...(state.pending_priority??[]),...state.objectives.map(item=>item.id)]);
  return ids.map(id=>state.objectives.find(item=>item.id===id))
    .filter(item=>item.status==='pending'&&item.depends_on.every(id=>satisfied(state,id)));
}
/** Conditional read-only view of an accepted reducer checkpoint, not a grant.
 * The actual assess transition must still commit before any work can execute.
 * A failed/limited recorded action cannot be marked met by this reducer.
 */
export function readyObjectivesAfterAssessment(state){
  if(state?.phase!=='assessing'||state.pending_action?.kind!=='assess')return [];
  const projected=copy(state),current=projected.objectives.find(item=>item.id===projected.pending_action.objective_id);
  if(current?.status!=='executed')return [];
  current.status='met';
  return readyObjectives(projected);
}
function batchReadyInvestigations(state) {
  const ready=readyObjectives(state);
  const eligible=item=>item?.mode==='execute'&&item.subtasks?.length>0&&!item.product_paths?.length&&!item.resolves.length;
  if(!eligible(ready[0]))return;
  // Equal consumer sets mean each consumer already requires ALL these scopes.
  // Do not add a barrier to a consumer that originally needed only one result.
  const consumers=id=>JSON.stringify(state.objectives.filter(item=>item.depends_on.includes(id)||
    item.resolves.includes(id)||item.supersession?.replacement_ids?.includes(id)).map(item=>item.id).sort());
  const key=consumers(ready[0].id),group=ready.filter(item=>eligible(item)&&consumers(item.id)===key);
  if(group.length<2)return;
  const ids=group.map(item=>item.id),selected=new Set(ids);
  const digest=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
  const id='host-ready-'+digest([state.attempt_id,state.round,ids]);
  const subtasks=group.flatMap(item=>{
    const names=new Map(item.subtasks.map(task=>[task.id,'branch-'+digest([item.id,task.id]).slice(0,24)]));
    return item.subtasks.map(task=>({...copy(task),id:names.get(task.id),title:item.id+': '+task.title,
      depends_on:task.depends_on.map(dependency=>names.get(dependency))}));
  });
  const batch={id,purpose:group.map(item=>item.purpose).join('; '),
    questions:unique(group.flatMap(item=>item.questions)),depends_on:unique(group.flatMap(item=>item.depends_on)),
    expected_outputs:unique(group.flatMap(item=>item.expected_outputs)),
    checks:group.flatMap(item=>item.checks.map(check=>item.id+': '+check)),mode:'execute',
    input_refs:unique(group.flatMap(item=>item.input_refs)),resolves:[],
    derived_from:unique(group.flatMap(item=>item.derived_from??[])),subtasks};
  validateCycleOperation({operation:'plan',goal:state.goal,output_mode:state.output_mode,objectives:[batch],source_refs:[]});
  for(const item of group){item.status='superseded';item.supersession={
    reason:'Host combined ready declared investigation graphs with the same downstream consumers; original questions and checks are retained.',replacement_ids:[id]};}
  state.objectives.push({...batch,status:'pending'});
  state.pending_priority=[id,...(state.pending_priority??[]).filter(value=>!selected.has(value))];
  validateGraph(state.objectives);
}
function activate(state,limits) {
  if(limits.batchReadyInvestigations===true)batchReadyInvestigations(state);
  const ready=readyObjectives(state)[0];
  requireCycle(ready,'No ready objective; this transition was not committed. Add a repair follow-up using resolves for incomplete work, explicitly supersede obsolete pending work, or declare a limited outcome. Unresolved work: '+JSON.stringify(unresolvedWork(state)));
  if(state.round>=limits.maxRounds) {
    if(limits.mode==='debug')capacity('research_rounds',state.round+1,limits.maxRounds);
    state.phase='limited';state.pending_action=null;
    state.limitations.push('Configured research round capacity reached; retained work remains available.');return;
  }
  state.pending_priority=(state.pending_priority??[]).filter(id=>id!==ready.id);
  state.round++;ready.status='running';state.phase='executing';state.pending_action=action(state,'execute',ready);
}
function unresolvedWork(state) {
  return state.objectives.filter(item=>!satisfied(state,item.id)).map(item=>({
    id:item.id,status:item.status,blocked_by:item.depends_on.filter(id=>!satisfied(state,id)),
    ...(item.supersession?{replacement_ids:item.supersession.replacement_ids}:{}),
  }));
}
function satisfied(state,id) {
  const objective=state.objectives.find(item=>item.id===id);
  if(objective.status==='met')return true;
  if(objective.status==='superseded')return objective.supersession.replacement_ids.every(replacement=>satisfied(state,replacement));
  const repairs=state.objectives.filter(item=>item.resolves.includes(id));
  return repairs.length>0&&repairs.every(item=>satisfied(state,item.id));
}
function checkedState(value,limits) {
  const state=copy(value);
  requireCycle(state.schema===SCHEMA&&phases.has(state.phase),'Invalid cycle state');
  state.owner=owner(state.owner);
  requireCycle(nonempty(state.attempt_id)&&Number.isSafeInteger(state.round)&&state.round>0,'Invalid cycle execution identity');
  requireCycle(Array.isArray(state.objectives)&&state.objectives.length>0&&state.objectives.every(item=>statuses.has(item.status))&&
    ['findings','product_refs','product_history','active_products','limitations','admitted_refs','successful_refs'].every(key=>Array.isArray(state[key])),'Invalid cycle state collections');
  requireCycle(state.active_products.every(item=>nonempty(item.path)&&nonempty(item.ref)&&
    state.product_history.some(previous=>previous.ref===item.ref&&previous.path===item.path))&&
    unique(state.active_products.map(item=>item.path)).length===state.active_products.length&&
    same(state.product_refs,state.active_products.map(item=>item.ref)),'Invalid active product projection');
  if(state.delivery_products!==undefined)requireCycle(Array.isArray(state.delivery_products)&&state.delivery_products.length>0&&
    unique(state.delivery_products.map(item=>item.path)).length===state.delivery_products.length&&
    state.delivery_products.every(item=>nonempty(item.path)&&nonempty(item.ref)&&state.product_history.some(previous=>previous.path===item.path&&previous.ref===item.ref)),
    'Invalid selected delivery products');
  state.pending_priority??=[];
  state.question_adoptions??=[];
  requireCycle(Array.isArray(state.question_adoptions)&&state.question_adoptions.every(item=>
    state.objectives.some(objective=>objective.id===item.objective_id)&&Array.isArray(item.questions)&&item.questions.length>0&&item.questions.every(nonempty)&&
    Array.isArray(item.derived_from)&&item.derived_from.length>0&&item.derived_from.every(id=>state.findings.some(finding=>finding.id===id))&&
    nonempty(item.assessment_action_id)&&Number.isSafeInteger(item.round)&&item.round>0),'Invalid adopted-question provenance');
  requireCycle(Array.isArray(state.pending_priority)&&unique(state.pending_priority).length===state.pending_priority.length&&
    state.pending_priority.every(id=>state.objectives.some(item=>item.id===id&&item.status==='pending')),'Invalid pending research priority');
  const definitions=state.objectives.map(({status,supersession,...definition})=>definition);
  for(const item of state.objectives)if(item.status==='superseded')requireCycle(item.supersession&&nonempty(item.supersession.reason)&&
    Array.isArray(item.supersession.replacement_ids)&&item.supersession.replacement_ids.length>0,'Invalid superseded objective history');
  validateCycleOperation({operation:'plan',goal:state.goal,output_mode:state.output_mode,objectives:definitions,source_refs:[]});
  validateGraph(state.objectives);
  if(['executing','assessing'].includes(state.phase)) {
    const item=state.objectives.find(item=>item.id===state.pending_action?.objective_id);
    // Older protected checkpoints predate these projections. Derive only
    // absent metadata from the accepted objective; never overwrite a mismatch.
    if(item)for(const [key,value] of Object.entries({questions:item.questions,derived_from:item.derived_from??[]}))
      if(!Object.hasOwn(state.pending_action,key))state.pending_action[key]=[...value];
    requireCycle(item&&same(state.pending_action,action(state,state.phase==='executing'?'execute':'assess',item)),'Invalid pending action binding');
  }else requireCycle(state.pending_action===null,'Terminal cycle has an active action');
  checkCapacity(state,limits);return state;
}
function requireRefs(refs,known,message) {
  requireCycle(unique(refs).length===refs.length&&refs.every(ref=>known.has(ref)),message);
}

export function reduceEnterpriseCycle(previous,input,host,options) {
  const limits=checkedLimits(options), command=validateCycleOperation(input), context=copy(host);
  const binding=owner(context.owner);
  requireCycle(nonempty(context.attempt_id)&&Array.isArray(context.sources)&&context.sources.every(nonempty)&&
    Array.isArray(context.receipts)&&Array.isArray(context.products),'Invalid host context');
  let state=previous===null?null:checkedState(previous,limits);
  const progressEvents=[];
  if(state)requireCycle(same(state.owner,binding)&&state.attempt_id===context.attempt_id,'Cycle owner or Attempt changed');
  const sources=new Set(context.sources);
  if(command.operation==='plan') {
    requireCycle(state===null,'Cycle already has an accepted plan');
    requireCycle(command.objectives.length>0,'Plan needs an objective');
    for(const item of command.objectives)requireCycle(item.resolves.length===0,
      `Objective ${publicId(item.id)}.resolves must be [] in an initial plan. Put questions in questions; resolves is only for assess.follow_ups repairing already assessed incomplete objective IDs.`);
    validateGraph(command.objectives);
    requireCycle(command.objectives.every(item=>(item.derived_from??[]).length===0),'Initial objective.derived_from must be [] or omitted; findings have not been recorded yet');
    requireRefs(command.source_refs,sources,'Plan source was not admitted');
    for(const item of command.objectives)requireRefs(item.input_refs,sources,'Objective input was not admitted');
    state={schema:SCHEMA,owner:binding,attempt_id:context.attempt_id,goal:command.goal,output_mode:command.output_mode,
      objectives:command.objectives.map(item=>({...item,status:'pending'})),round:0,phase:'executing',pending_action:null,
      findings:[],pending_priority:[],question_adoptions:[],product_refs:[],active_products:[],product_history:[],limitations:[],admitted_refs:unique([...sources]),successful_refs:unique([...sources]),last_assessment:null};
    activate(state,limits);
  }else {
    requireCycle(state!==null,'Plan must be committed before work');
    requireCycle(state.pending_action&&command.action_id===state.pending_action.id,'Action does not match current pending action');
    const objective=state.objectives.find(item=>item.id===state.pending_action.objective_id);
    if(command.operation==='record') {
      requireCycle(state.phase==='executing','Work can be recorded only during execution');
      const receipts=context.receipts.filter(item=>item.action_id===command.action_id&&item.attempt_id===state.attempt_id);
      requireCycle(receipts.every(item=>nonempty(item.ref)&&['completed','failed','cancelled','unknown'].includes(item.status)),'Invalid execution receipt');
      requireCycle(unique(receipts.map(item=>item.ref)).length===receipts.length,'Duplicate execution receipt');
      const successful=new Set([...state.successful_refs,...sources,...receipts.filter(item=>item.status==='completed').map(item=>item.ref)]);
      const known=new Set([...successful,...state.admitted_refs,...receipts.map(item=>item.ref)]);
      const products=context.products.filter(item=>item.action_id===command.action_id&&item.attempt_id===state.attempt_id&&item.status==='ready');
      requireRefs(command.product_refs,new Set(products.map(item=>item.ref)),'Product was not inspected for this action');
      const selectedProducts=command.product_refs.map(ref=>{
        const matches=products.filter(item=>item.ref===ref);
        requireCycle(matches.length===1&&nonempty(matches[0].path),'Product needs one inspected canonical path');
        return matches[0];
      });
      requireCycle(unique(selectedProducts.map(item=>item.path)).length===selectedProducts.length,'One action cannot publish two current versions of the same path');
      for(const product of selectedProducts)requireCycle(state.product_history.every(item=>item.ref!==product.ref||item.path===product.path),'Immutable product reference changed path');
      if(command.outcome==='completed') {
        const synthesis=objective.mode==='synthesis'&&objective.input_refs.length>0&&objective.input_refs.every(ref=>successful.has(ref))&&
          (command.findings.length>0||command.product_refs.length>0);
        requireCycle(receipts.some(item=>item.status==='completed')||synthesis,'Completed work needs an actual successful receipt or sourced synthesis');
      }else requireCycle(command.limitations.length>0,'Incomplete work needs explicit limitations');
      requireCycle(unique(command.findings.map(item=>item.id)).length===command.findings.length,'Duplicate finding identity');
      for(const finding of command.findings) {
        requireRefs(finding.refs,successful,'Finding reference was not successfully admitted');
        requireCycle(finding.status==='hypothesis'||finding.refs.length>0,'Supported or refuted finding needs sources');
      }
      const findings=new Map(state.findings.map(item=>[item.id,item]));
      for(const finding of command.findings) {
        requireCycle(!findings.has(finding.id)||same(findings.get(finding.id),finding),'Retained finding is immutable; use a new finding identity for a revision');
        findings.set(finding.id,finding);
      }
      state.findings=[...findings.values()];
      const activeProducts=new Map(state.active_products.map(item=>[item.path,item]));
      for(const product of selectedProducts) {
        const history={ref:product.ref,path:product.path,producer_action_id:command.action_id,attempt_id:state.attempt_id};
        if(!state.product_history.some(item=>same(item,history)))state.product_history.push(history);
        activeProducts.set(product.path,{path:product.path,ref:product.ref});
      }
      state.active_products=[...activeProducts.values()];state.product_refs=state.active_products.map(item=>item.ref);
      state.limitations=unique([...state.limitations,...command.limitations]);
      state.admitted_refs=unique([...known,...command.product_refs]);state.successful_refs=unique([...successful,...command.product_refs]);
      objective.status=command.outcome==='completed'?'executed':command.outcome==='failed'?'failed':'limited';
      state.phase='assessing';state.pending_action=action(state,'assess',objective);
    }else {
      requireCycle(state.phase==='assessing','Assessment requires a separately recorded result');
      const known=new Set([...state.admitted_refs,...sources]),successful=new Set([...state.successful_refs,...sources]);
      requireCycle(command.coverage.length===1&&command.coverage[0].objective_id===objective.id,'Assessment must cover the active objective exactly once');
      const coverage=command.coverage[0];requireRefs(coverage.refs,known,'Unknown coverage reference');
      requireCycle(command.checks.length===unique(command.checks.map(item=>item.description)).length,'Duplicate assessment check');
      for(const check of command.checks) {
        requireRefs(check.refs,check.status==='passed'?successful:known,'Unknown check reference');
        if(check.status==='passed')requireCycle(check.refs.length>0,'Passed check needs an actual observation');
      }
      if(coverage.status==='met') {
        requireRefs(coverage.refs,successful,'Successful coverage needs admitted successful observations');
        requireCycle(objective.status==='executed'&&coverage.refs.length>0,'Met objective needs completed work and observed support');
        for(const [index,description] of objective.checks.entries())requireCycle(
          command.checks.some(check=>check.description===description&&check.status==='passed'),
          `Objective ${publicId(objective.id)}.checks[${index}] was not passed. assess.checks[].description must exactly copy the accepted label from pending_action.checks[${index}], with status=passed and successful admitted observation refs. Otherwise mark coverage partial or unmet and repair or report limits.`);
      }
      objective.status=coverage.status==='met'?'met':coverage.status==='partial'?'partial':objective.status==='failed'?'failed':'limited';
      // A settled partial/failed action is not successful TaskProgress completion.
      // The adapter projects this typed lifecycle without discarding outcome.
      const metadata=item=>({questions:[...item.questions],expected_outputs:[...item.expected_outputs],derived_from:[...(item.derived_from??[])]});
      const nextReason=command.reflection?.next_step_reason;
      progressEvents.push({step_id:objective.id,phase:'settled',outcome:objective.status,text:objective.purpose,
        result_summary:command.summary,...metadata(objective),...(nextReason?{next_action_reason:nextReason}:{})});
      state.last_assessment=command;
      requireCycle(command.decision==='revise'||command.decision==='continue'||command.follow_ups.length===0,'Terminal assessment cannot add follow-up work');
      const adoptions=command.question_adoptions??[];
      if(command.decision==='revise')requireCycle(command.follow_ups.length>0||adoptions.length>0,'Revise needs a concrete follow-up or pending-question adoption');
      const findingIds=new Set(state.findings.map(item=>item.id));
      const reflection=command.reflection??{};
      requireRefs(reflection.discoveries??[],findingIds,'Reflection discovery must reference a committed finding ID');
      for(const question of reflection.unresolved_questions??[])requireRefs(question.derived_from,findingIds,'Open-question provenance must reference committed finding IDs');
      for(const conflict of reflection.contradictions??[]) {
        requireCycle(conflict.finding_ids.length>0,'A contradiction needs committed finding IDs');
        requireRefs(conflict.finding_ids,findingIds,'Contradiction must reference committed finding IDs');
      }
      for(const item of command.follow_ups) {
        requireRefs(item.derived_from??[],findingIds,'New-question provenance must reference committed finding IDs');
        requireRefs(item.input_refs,successful,'Follow-up input was not admitted');
        requireCycle(item.resolves.every(id=>state.objectives.some(target=>target.id===id&&['partial','failed','limited'].includes(target.status))),
          'A repair must resolve an existing assessed incomplete objective');
      }
      const supersedes=command.supersedes??[];
      requireCycle(['continue','revise'].includes(command.decision)||supersedes.length===0,'Only continuing research may replace pending objectives');
      requireCycle(unique(supersedes.map(item=>item.objective_id)).length===supersedes.length,'An objective may be superseded only once in an assessment');
      for(const replacement of supersedes) {
        const old=state.objectives.find(item=>item.id===replacement.objective_id);
        requireCycle(old?.status==='pending','Only an unexecuted pending objective may be superseded');
        requireCycle(replacement.replacement_ids.length>0&&unique(replacement.replacement_ids).length===replacement.replacement_ids.length&&
          replacement.replacement_ids.every(id=>command.follow_ups.some(item=>item.id===id)),'Replacement IDs must name new follow-up objectives');
        old.status='superseded';old.supersession={reason:replacement.reason,replacement_ids:[...replacement.replacement_ids]};
      }
      requireCycle(['continue','revise'].includes(command.decision)||adoptions.length===0,'Only continuing research may adopt questions into future work');
      for(const adoption of adoptions) {
        const target=state.objectives.find(item=>item.id===adoption.objective_id);
        requireCycle(target?.status==='pending',`Question adoption target ${publicId(adoption.objective_id)} must be an existing pending objective`);
        requireCycle(adoption.questions.length>0&&adoption.derived_from.length>0,'Question adoption needs nonempty questions and committed finding IDs');
        const ids=unique(adoption.derived_from),questions=unique(adoption.questions);
        requireCycle(ids.every(id=>{
          const finding=state.findings.find(item=>item.id===id);
          return finding&&finding.refs.length>0&&finding.refs.every(ref=>state.successful_refs.includes(ref));
        }),'Question adoption provenance requires committed findings with successful source observations');
        const added=questions.filter(question=>!target.questions.includes(question));
        const hasNewOrigin=ids.some(id=>!(target.derived_from??[]).includes(id));
        target.questions=unique([...target.questions,...questions]);
        target.derived_from=unique([...(target.derived_from??[]),...ids]);
        if(added.length||hasNewOrigin)state.question_adoptions.push({objective_id:target.id,
          questions:added.length?added:questions,derived_from:ids,assessment_action_id:command.action_id,round:state.round});
      }
      state.pending_priority=unique([...command.follow_ups.map(item=>item.id),...state.pending_priority]).filter(id=>
        !supersedes.some(item=>item.objective_id===id));
      state.objectives.push(...command.follow_ups.map(item=>({...item,status:'pending'})));validateGraph(state.objectives);
      if(command.delivery_product_refs!==undefined){
        requireCycle(state.output_mode==='files'&&['deliver','limited'].includes(command.decision),'Final delivery selection is only valid for file deliver or limited assessment');
        requireCycle(command.delivery_product_refs.length>0&&unique(command.delivery_product_refs).length===command.delivery_product_refs.length,'Final delivery selection must be nonempty and unique');
        state.delivery_products=command.delivery_product_refs.map(ref=>{
          const active=state.active_products.find(item=>item.ref===ref);
          requireCycle(active&&context.products.some(item=>item.ref===ref&&item.path===active.path&&item.status==='ready'),'Final delivery product must be previously registered and currently inspected');
          return copy(active);
        });
      }
      if(command.decision==='deliver') {
        requireCycle(state.objectives.every(item=>satisfied(state,item.id)),'Unresolved objectives require continuation or limited delivery; this assessment was not committed. Complete pending work, repair incomplete work using follow_ups.resolves, or explicitly supersede obsolete pending work. Unresolved work: '+JSON.stringify(unresolvedWork(state)));
      }
      if(['deliver','limited'].includes(command.decision)&&state.output_mode==='files'){
          const finalProducts=state.delivery_products??state.active_products;
          requireCycle(command.decision==='limited'||finalProducts.length>0,'Delivery requires inspected current saved products');
          const mismatches=finalProducts.flatMap(product=>{
            if(context.products.some(item=>item.ref===product.ref&&item.path===product.path&&item.status==='ready'))return [];
            const current=context.products.find(item=>item.path===product.path&&item.status==='ready');
            return [{path:product.path,registered_ref:product.ref,current_ref:current?.ref??null,status:current?'changed':'unavailable'}];
          });
          if(mismatches.length){
            const error=new EnterpriseCycleError('research_product_version_mismatch',
              'Saved product versions differ from the registered versions or are unavailable. For limited delivery, select only usable previously recorded current paths using delivery_product_refs and explain excluded files. Do not claim changed or missing files were delivered. To deliver a changed file, verify only the listed paths, then use a follow-up action to record their actual current bytes before a separate assessment. Preserve unchanged products; do not rebuild them merely to refresh registration. Re-registration does not establish content quality.');
            const diagnostic={total:mismatches.length,truncated:false,products:[]};
            // Reuse the accepted control-document budget, without a new item or
            // path-length limit. Omitted entries remain included in total.
            for(const item of mismatches){
              diagnostic.products.push(item);
              if(Buffer.byteLength(JSON.stringify({...diagnostic,truncated:true}))>limits.snapshotBytes){diagnostic.products.pop();diagnostic.truncated=true;break;}
            }
            error.product_mismatches=diagnostic;throw error;
          }
      }
      if(command.decision==='deliver') {
        state.phase='done';state.pending_action=null;
      }else if(['limited','blocked'].includes(command.decision)) {
        state.phase=command.decision;state.pending_action=null;state.limitations=unique([...state.limitations,command.summary]);
      }else activate(state,limits);
    }
  }
  checkCapacity(state,limits);
  const current=state.pending_action, active=current?state.objectives.find(item=>item.id===current.objective_id):null;
  const nextReason=state.last_assessment?.reflection?.next_step_reason;
  const progress=active?{step_id:active.id,phase:current.kind==='execute'?'started':'updated',text:active.purpose,
    questions:[...active.questions],expected_outputs:[...active.expected_outputs],derived_from:[...(active.derived_from??[])],
    ...(nextReason?{next_action_reason:nextReason}:{})}:null;
  if(progress)progressEvents.push(progress);
  return {state,pending_action:current?copy(current):null,
    progress,progress_events:progressEvents};
}
