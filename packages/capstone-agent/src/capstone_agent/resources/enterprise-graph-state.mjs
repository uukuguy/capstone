/** Pure model-owned graph transitions. The host is the sole CAS writer.
 *
 * Host context: {owner,attempt_id,sources,receipts,products,results?,computation?}.
 * sources: opaque strings or {ref,revision,owner?}; strings have unavailable
 * version information, never an invented hash. External results must be complete
 * immutable manifests with the exact owner; presence is the host's grant.
 * receipts: {ref,owner?,action_id,attempt_id,status}; products use the same
 * identity plus status:'ready'. The host inspects artifacts BEFORE admission.
 * computation: {action_id?,source_versions:[{ref,revision}],method:{ref,revision,
 * parameters_sha256?,environment_ref?,environment_unavailable?}|{unavailable}}.
 * No supplied method means explicitly unavailable provenance, never a guess.
 *
 * Returned events are proposals. Bind them to the committed checkpoint before
 * emitting. Persist start intent and frozen inputs before native execution.
 * execution_settled is a host-only dispatch event, not successful assessment.
 * Retries of start/settle/record/assess preserve issued action identities; command
 * replay for plan/revise stays with the existing CAS command adapter.
 */
import {createHash} from 'node:crypto';
import {requireCycle} from './enterprise-cycle-contract.mjs';
import {GRAPH_SCHEMA,RESULT_SCHEMA,GRAPH_WORK_EDITION,validateGraphOperation,graphCapacity,graphLimits} from './enterprise-graph-contract.mjs';

const clone=value=>structuredClone(value);
const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?
  Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
const same=(left,right)=>JSON.stringify(canonical(left))===JSON.stringify(canonical(right));
const digest=value=>createHash('sha256').update(JSON.stringify(canonical(value))).digest('hex');
const reference=(kind,value)=>kind+':'+digest(value);
const unique=values=>new Set(values).size===values.length;
const nonempty=value=>typeof value==='string'&&value.trim().length>0;
const opaque=value=>typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$/.test(value);
const settled=new Set(['success','limited','failure']);
function checkedOwner(value) {
  requireCycle(value&&Object.keys(value).sort().join(',')==='goal_revision,research_id,thread_id,work_id'&&
    ['thread_id','work_id','research_id'].every(key=>opaque(value[key]))&&Number.isSafeInteger(value.goal_revision)&&value.goal_revision>0,'Invalid graph owner');
  return clone(value);
}
function hostContext(host,state) {
  const owner=checkedOwner(host?.owner);
  requireCycle(opaque(host.attempt_id)&&['sources','receipts','products'].every(key=>Array.isArray(host[key])),'Invalid admitted graph context');
  if(state)requireCycle(same(owner,state.owner)&&host.attempt_id===state.attempt_id,'Graph owner or Attempt mismatch');
  if(state?.selected_limited_inputs)requireCycle(host.allow_selected_limited_inputs===true,'Selected limited inputs require the host policy');
  requireCycle(host.graph_work_edition===undefined||host.graph_work_edition===GRAPH_WORK_EDITION,'Unsupported graph work edition');
  if(state)requireCycle(state.work_edition===host.graph_work_edition,'Graph work edition does not match its accepted checkpoint');
  const sources=host.sources.map(item=>typeof item==='string'?{ref:item,revision:null}:item);
  requireCycle(sources.every(item=>opaque(item?.ref)&&(!item.owner||same(item.owner,owner))&&
    (item.revision===null||opaque(item.revision))),'Invalid source grant');
  requireCycle(unique(sources.map(item=>item.ref)),'Duplicate source grants');
  return {...host,owner,sources,results:host.results??[]};
}
function nodeFor(state,id){const node=state.nodes.find(item=>item.id===id);requireCycle(node,'Unknown model node');return node;}
function resultFor(state,ref){return [...state.results,...state.external_results].find(item=>item.result_ref===ref);}
function requireResult(state,ref){const result=resultFor(state,ref);requireCycle(result,'Result was not admitted');return result;}
function successfulResult(state,ref,input){
  const result=requireResult(state,ref);
  if(state.external_results.some(item=>item.result_ref===ref))return result;
  const execution=state.executions.find(item=>item.execute_action_id===result.producer.action_id);
  if(execution?.phase!=='success')limitedAcceptance(state,input,result);
  return result;
}
function limitedAcceptance(state,input,result){
  const execution=executionFor(state,result.producer.step_id,result.producer.execution_revision),current=state.node_states[result.producer.step_id];
  const selected=state.selected_limited_inputs===true&&!input?.accept_limited;
  requireCycle((selected||state.work_edition===GRAPH_WORK_EDITION&&input?.result_ref===result.result_ref&&input.accept_limited&&
    execution?.assessment_ref===input.accept_limited.assessment_ref)&&
    execution?.phase==='limited'&&execution.settled_status==='completed'&&execution.assessment?.outcome==='limited'&&
    execution.execute_action_id===result.producer.action_id&&execution.output_bindings.some(item=>item.result_ref===result.result_ref&&item.slot===result.slot)&&
    current?.execute_action_id===execution.execute_action_id&&
    current.applicability==='current','Input result producer has not passed assessment or lacks exact limited acceptance');
  return {result_ref:result.result_ref,producer_action_id:execution.execute_action_id,producer_execution_revision:execution.execution_revision,
    assessment_ref:execution.assessment_ref,assessment_summary:execution.assessment.summary,record_limitations:clone(execution.record.limitations),
    unmet_checks:clone(execution.assessment.checks.filter(item=>item.status!=='passed')),
    rationale:input?.accept_limited?.rationale??'The research task selected this retained result; its limitations remain visible.'};
}
function checkedMethod(value,limits){
  const method=clone(value);
  requireCycle(method&&typeof method==='object'&&!Array.isArray(method)&&Object.getPrototypeOf(method)===Object.prototype,'Invalid method provenance');
  if(method.unavailable)requireCycle(Object.keys(method).length===1&&nonempty(method.unavailable),'Invalid unavailable method provenance');
  else{
    requireCycle(Object.keys(method).every(key=>['ref','revision','parameters_sha256','environment_ref','environment_unavailable'].includes(key))&&
      opaque(method.ref)&&opaque(method.revision),'Method needs an admitted exact identity');
    requireCycle(method.parameters_sha256===undefined||/^[a-f0-9]{64}$/.test(method.parameters_sha256),'Invalid method parameter digest');
    requireCycle((opaque(method.environment_ref)&&method.environment_unavailable===undefined)||
      (!method.environment_ref&&nonempty(method.environment_unavailable)),'Method needs exact environment or explicit unavailability');
  }
  for(const value of Object.values(method))if(typeof value==='string')graphCapacity('graph_text',value.length,limits.maxText);
  return method;
}
function checkedSourceVersions(versions,limits){
  requireCycle(Array.isArray(versions),'Source versions must be admitted');graphCapacity('graph_items',versions.length,limits.maxItems);
  for(const version of versions)requireCycle(version&&Object.keys(version).sort().join(',')==='ref,revision'&&
    opaque(version.ref)&&opaque(version.revision),'Invalid source version manifest');
  requireCycle(unique(versions.map(item=>item.ref+'\0'+item.revision)),'Duplicate source versions');
  return clone(versions);
}
function admitResults(state,host,limits){
  requireCycle(Array.isArray(host.results),'Invalid external result grants');
  for(const result of host.results){
    requireCycle(result?.schema===RESULT_SCHEMA&&opaque(result.result_ref)&&same(result.owner,state.owner),'Cross-owner or invalid result grant');
    requireCycle(Object.keys(result).sort().join(',')===['schema','result_ref','owner','producer','slot','kind','source_versions','method',
      'consumed_results','observation_refs','artifact_refs','supersedes','summary','scope','recompute_reason',
      ...((state.work_edition||state.selected_limited_inputs)&&result.input_limitations!==undefined?['input_limitations']:[])].sort().join(','),
      'Unexpected or missing result manifest fields');
    requireCycle(result.producer&&opaque(result.producer.step_id)&&opaque(result.producer.action_id)&&opaque(result.producer.attempt_id)&&
      Object.keys(result.producer).every(key=>['step_id','action_id','attempt_id','execution_revision','definition_ref'].includes(key))&&
      (result.producer.definition_ref===undefined||opaque(result.producer.definition_ref))&&
      Number.isSafeInteger(result.producer.execution_revision)&&result.producer.execution_revision>0&&opaque(result.slot)&&
      ['observation','artifact'].includes(result.kind)&&Array.isArray(result.source_versions)&&result.method&&
      ['consumed_results','observation_refs','artifact_refs','supersedes'].every(key=>Array.isArray(result[key])&&result[key].every(opaque))&&
      nonempty(result.summary)&&nonempty(result.scope),'External result needs a complete immutable manifest');
    checkedSourceVersions(result.source_versions,limits);checkedMethod(result.method,limits);
    if(result.input_limitations!==undefined){
      requireCycle(Array.isArray(result.input_limitations),'Invalid inherited result limitations');
      graphCapacity('graph_items',result.input_limitations.length,limits.maxItems);
      for(const item of result.input_limitations){
        requireCycle(item&&Object.keys(item).sort().join(',')===
          'assessment_ref,assessment_summary,producer_action_id,producer_execution_revision,rationale,record_limitations,result_ref,unmet_checks'&&
          ['assessment_ref','producer_action_id','result_ref'].every(key=>opaque(item[key]))&&
          Number.isSafeInteger(item.producer_execution_revision)&&item.producer_execution_revision>0&&nonempty(item.rationale)&&nonempty(item.assessment_summary)&&
          Array.isArray(item.record_limitations)&&item.record_limitations.every(nonempty)&&Array.isArray(item.unmet_checks)&&
          item.unmet_checks.every(check=>check&&Object.keys(check).sort().join(',')==='description,explanation,refs,status'&&
            nonempty(check.description)&&nonempty(check.explanation)&&['failed','not_run'].includes(check.status)&&
            Array.isArray(check.refs)&&check.refs.every(opaque)),'Invalid inherited limitation provenance');
        graphCapacity('graph_text',item.rationale.length,limits.maxText);
        graphCapacity('graph_text',item.assessment_summary.length,limits.maxText);
        for(const text of [...item.record_limitations,...item.unmet_checks.flatMap(check=>[check.description,check.explanation])])
          graphCapacity('graph_text',text.length,limits.maxText);
        for(const list of [item.record_limitations,item.unmet_checks,...item.unmet_checks.map(check=>check.refs)])graphCapacity('graph_items',list.length,limits.maxItems);
      }
    }
    if(result.recompute_reason!==null){
      const reason=result.recompute_reason;
      requireCycle(reason&&Object.keys(reason).every(key=>['kind','refs','diagnostic'].includes(key))&&
        ['source_changed','method_changed','missing_result','discrepancy'].includes(reason.kind)&&Array.isArray(reason.refs)&&
        reason.refs.every(opaque)&&unique(reason.refs)&&(reason.diagnostic===undefined||nonempty(reason.diagnostic)),
        'Invalid result recompute reason manifest');
      graphCapacity('graph_items',reason.refs.length,limits.maxItems);
      if(reason.diagnostic)graphCapacity('graph_text',reason.diagnostic.length,limits.maxText);
    }
    for(const key of ['consumed_results','observation_refs','artifact_refs','supersedes']){
      graphCapacity('graph_items',result[key].length,limits.maxItems);requireCycle(unique(result[key]),'Duplicate result manifest references');
    }
    requireCycle(result.kind==='observation'?result.observation_refs.length>0:result.artifact_refs.length>0,'Result manifest lacks declared content');
    graphCapacity('graph_text',result.summary.length,limits.maxText);graphCapacity('graph_text',result.scope.length,limits.maxText);
    const previous=resultFor(state,result.result_ref);
    requireCycle(!previous||same(previous,result),'Immutable result grant changed');
    if(!previous)state.external_results.push(clone(result));
  }
}
function validateGraph(state,nodes,context={}){
  requireCycle(unique(nodes.map(item=>item.id)),'Duplicate model node ID');
  const byId=new Map(nodes.map(item=>[item.id,item]));
  for(const node of nodes){
    requireCycle(Array.isArray(node.source_refs)&&unique(node.source_refs)&&node.source_refs.every(ref=>state.source_refs.includes(ref)),
      'Node source selection must be a unique subset of graph-admitted original sources');
    requireCycle(node.questions.length>0&&node.expected_outputs.length>0,'Node needs questions and expected outputs');
    requireCycle(unique(node.depends_on)&&unique(node.checks)&&unique(node.outputs.map(item=>item.slot))&&
      unique(node.inputs.map(item=>item.name))&&unique(node.inputs.map(item=>item.result_ref?['ref',item.result_ref].join('\0'):
        ['slot',item.from.step_id,item.from.slot].join('\0'))),'Duplicate dependency, check, output slot or input binding');
    requireCycle(node.mode!=='synthesis'||node.inputs.length>0||
      (context.incremental_source_selection===true&&node.source_refs.length>0),'Synthesis needs selected result inputs');
    for(const dependency of node.depends_on)requireCycle(byId.has(dependency),'Unknown declared dependency');
    for(const input of node.inputs){
      if(input.result_ref){
        const result=requireResult(state,input.result_ref);
        const local=state.results.some(item=>item.result_ref===input.result_ref);
        requireCycle(!local||node.depends_on.includes(result.producer.step_id),'Result input requires its declared producer dependency');
        // Started consumers retain their exact frozen acceptance when another
        // producer version is selected later. New bindings require live review.
        if(input.accept_limited&&!(state.node_states[node.id]?.execute_action_id&&
          state.nodes.find(item=>item.id===node.id)?.inputs.some(prior=>same(prior,input))))limitedAcceptance(state,input,result);
      }else{
        requireCycle(node.depends_on.includes(input.from.step_id),'Future slot requires an explicit dependency');
        const producer=byId.get(input.from.step_id);
        requireCycle(producer?.outputs.some(output=>output.slot===input.from.slot),'Unknown producer or output slot');
      }
    }
  }
  const visiting=new Set(),visited=new Set();
  function visit(id){requireCycle(!visiting.has(id),'Graph contains a dependency cycle');if(visited.has(id))return;
    visiting.add(id);for(const target of byId.get(id).depends_on)visit(target);visiting.delete(id);visited.add(id);}
  for(const id of byId.keys())visit(id);
}
function emptyNode(state,node,revision=1,rerun=null,hostSources=[]){
  const selected=node.source_refs.map(ref=>hostSources.find(item=>item.ref===ref)??state.source_versions.find(item=>item.ref===ref))
    .filter(item=>item&&item.revision!==null).map(({ref,revision})=>({ref,revision}));
  return {phase:'pending',applicability:'current',stale_reason:null,execution_revision:revision,
    definition_ref:reference('node',{owner:state.owner,node}),execute_action_id:null,assess_action_id:null,
    selected_source_versions:selected,input_bindings:[],output_bindings:[],input_targets:[],dependency_targets:[],blocked_by:[],wait_reason:null,
    recompute_reason:rerun?.reason??null,supersedes:rerun?.supersedes??[]};
}
function selectTargets(state,id){
  const node=nodeFor(state,id),current=state.node_states[id];
  current.dependency_targets=node.depends_on.map(step_id=>({step_id,execution_revision:state.node_states[step_id].execution_revision}));
  current.input_targets=node.inputs.filter(item=>item.from).map(item=>({name:item.name,...item.from,
    execution_revision:state.node_states[item.from.step_id].execution_revision}));
}
function executionFor(state,id,revision){return state.executions.find(item=>item.step_id===id&&item.execution_revision===revision);}
function waiting(state,node,current){
  const blocked=current.dependency_targets.filter(target=>{
    const execution=executionFor(state,target.step_id,target.execution_revision),producer=nodeFor(state,target.step_id);
    const targetState=state.node_states[target.step_id];
    if(execution?.phase==='limited'&&state.selected_limited_inputs){
      if(targetState.applicability!=='current'||execution.settled_status!=='completed')return true;
      const selected=node.inputs.filter(input=>input.from?.step_id===target.step_id||
        input.result_ref&&requireResult(state,input.result_ref).producer.step_id===target.step_id);
      try{
        for(const input of selected){
          const ref=input.result_ref??execution.output_bindings.find(item=>item.slot===input.from.slot)?.result_ref;
          if(!ref)return true;
          limitedAcceptance(state,input,requireResult(state,ref));
        }
        return false;
      }catch{return true;}
    }
    if(execution?.phase==='limited'&&state.work_edition===GRAPH_WORK_EDITION){
      const selected=node.inputs.filter(input=>input.result_ref&&requireResult(state,input.result_ref).producer.step_id===target.step_id);
      if(!selected.length||node.inputs.some(input=>input.from?.step_id===target.step_id))return true;
      try{for(const input of selected)limitedAcceptance(state,input,requireResult(state,input.result_ref));return false;}catch{return true;}
    }
    return !execution||execution.phase!=='success'||targetState.applicability==='stale'||
      producer.outputs.some(output=>!execution.output_bindings.some(item=>item.slot===output.slot));
  }).map(item=>item.step_id);
  for(const target of current.input_targets){
    const execution=executionFor(state,target.step_id,target.execution_revision);
    if(!execution?.output_bindings.some(item=>item.slot===target.slot)&&!blocked.includes(target.step_id))blocked.push(target.step_id);
  }
  for(const input of node.inputs.filter(item=>item.result_ref)){
    const result=requireResult(state,input.result_ref);
    if(state.results.some(item=>item.result_ref===input.result_ref)){
      const execution=executionFor(state,result.producer.step_id,result.producer.execution_revision);
      if(execution?.phase!=='success'&&!blocked.includes(result.producer.step_id)){
        try{limitedAcceptance(state,input,result);}catch{blocked.push(result.producer.step_id);}
      }
    }
  }
  return blocked;
}
function refresh(state){
  for(const node of state.nodes){
    const current=state.node_states[node.id];
    if(current.execute_action_id||current.applicability==='stale')continue;
    current.blocked_by=waiting(state,node,current);current.phase=current.blocked_by.length?'pending':'ready';
    current.wait_reason=current.blocked_by.length?'dependencies':null;
  }
}
function bindInputs(state,node,current){
  return node.inputs.map(input=>{
    let result;
    if(input.result_ref)result=successfulResult(state,input.result_ref,input);
    else{
      const target=current.input_targets.find(item=>item.name===input.name),execution=executionFor(state,target.step_id,target.execution_revision);
      const binding=execution?.output_bindings.find(item=>item.slot===target.slot);
      requireCycle(binding,'Required output has not been persisted');result=successfulResult(state,binding.result_ref);
    }
    const execution=state.executions.find(item=>item.execute_action_id===result.producer.action_id);
    const acceptance=input.accept_limited||state.selected_limited_inputs&&execution?.phase==='limited'
      ?limitedAcceptance(state,input,result):undefined;
    return {input_name:input.name,producer_step_id:result.producer.step_id,slot:result.slot,result_ref:result.result_ref,
      ...(acceptance?{accepted_limitations:acceptance}:{}),
      source_versions:clone(result.source_versions),method_ref:result.method.ref??null,selected_at_graph_revision:state.graph_revision};
  });
}
function issueAction(state,node,current,kind){
  requireCycle(Array.isArray(node.source_refs)&&Array.isArray(current.selected_source_versions),
    'Explicit node source selection is required; revise an unstarted legacy graph or replan the task');
  const action={owner:clone(state.owner),attempt_id:state.attempt_id,step_id:node.id,kind,
    definition_ref:current.definition_ref,execution_revision:current.execution_revision,graph_ref:state.graph_ref,
    graph_revision:state.graph_revision,source_refs:clone(node.source_refs),source_versions:clone(current.selected_source_versions),
    input_bindings:clone(current.input_bindings)};
  action.id=reference('action',action);state.actions.push(action);return action;
}
/** Exact frozen action lease; no fallback to a most-recent/global action. */
export function graphAction(state,actionId){
  requireCycle(state?.schema===GRAPH_SCHEMA,'Explicit graph v2 checkpoint required');
  const action=state.actions.find(item=>item.id===actionId);requireCycle(action,'Unknown graph action');return clone(action);
}
function activeAction(state,id,kind){
  const action=graphAction(state,id);requireCycle(action.kind===kind,'Wrong node action kind');
  const current=state.node_states[action.step_id];
  requireCycle(current.execution_revision===action.execution_revision&&current.definition_ref===action.definition_ref&&
    current[kind==='execute'?'execute_action_id':'assess_action_id']===id,'Action is not the current node execution');
  return {action,current,node:nodeFor(state,action.step_id),execution:executionFor(state,action.step_id,action.execution_revision)};
}
function graphCommit(state,reason){
  const entry={graph_revision:state.graph_revision,previous_graph_ref:state.graph_ref??null,nodes:clone(state.nodes),reason,
    selections:state.nodes.map(node=>({step_id:node.id,definition_ref:state.node_states[node.id].definition_ref,
      execution_revision:state.node_states[node.id].execution_revision,input_targets:clone(state.node_states[node.id].input_targets),
      dependency_targets:clone(state.node_states[node.id].dependency_targets)}))};
  state.graph_ref=reference('graph',{owner:state.owner,attempt_id:state.attempt_id,goal:state.goal,output_mode:state.output_mode,
    source_refs:state.source_refs,source_versions:state.source_versions,...entry});
  state.revisions.push({...entry,graph_ref:state.graph_ref});state.revision_reason=reason;
  return {kind:'graph_committed',graph_ref:state.graph_ref,graph_revision:state.graph_revision,
    previous_graph_ref:entry.previous_graph_ref,nodes:clone(state.nodes),model_revision_reason:reason};
}
function admittedForAction(host,action){
  const filter=items=>items.filter(item=>item.action_id===action.id&&item.attempt_id===action.attempt_id);
  const receipts=filter(host.receipts),products=filter(host.products);
  requireCycle([...receipts,...products].every(item=>opaque(item.ref)&&(!item.owner||same(item.owner,action.owner))),
    'Cross-owner or invalid action admission');
  requireCycle(receipts.every(item=>['completed','failed','cancelled','unknown'].includes(item.status))&&unique(receipts.map(item=>item.ref))&&
    products.every(item=>item.status==='ready')&&unique(products.map(item=>item.ref)),'Invalid or duplicate action admission');
  return {receipts,products};
}
function computationContext(state,host,action,bindings,limits){
  requireCycle(Array.isArray(action.source_refs)&&Array.isArray(action.source_versions),
    'Legacy action has no explicit source selection; reconcile or replan the task');
  const context=host.computation;
  requireCycle(!context?.action_id||context.action_id===action.id,'Computation belongs to another action');
  const inherited=bindings.flatMap(binding=>requireResult(state,binding.result_ref).source_versions);
  const selected=[...action.source_versions,...inherited];
  const versions=context?.source_versions??[...new Map(selected.map(item=>[item.ref+'\0'+item.revision,item])).values()];
  checkedSourceVersions(versions,limits);
  const known=new Set(selected.map(item=>item.ref+'\0'+item.revision));
  for(const version of versions)requireCycle(version&&Object.keys(version).sort().join(',')==='ref,revision'&&opaque(version.ref)&&
    opaque(version.revision)&&known.has(version.ref+'\0'+version.revision),'Source version was not admitted');
  const source_versions=[...new Map([...selected,...versions].map(item=>[item.ref+'\0'+item.revision,{ref:item.ref,revision:item.revision}])).values()];
  checkedSourceVersions(source_versions,limits);
  const method=checkedMethod(context?.method??{unavailable:'Host did not supply method or environment identity'},limits);
  return {source_versions,method};
}
function markStale(state,newResult,events){
  if(!newResult.supersedes.length)return;
  const oldRefs=new Set(newResult.supersedes),affected=new Set();
  for(const node of state.nodes){
    if(node.id===newResult.producer.step_id)continue;
    const current=state.node_states[node.id];
    if(current.input_bindings.some(binding=>oldRefs.has(binding.result_ref))||
      current.dependency_targets.some(target=>newResult.supersedes.some(ref=>{
        const old=requireResult(state,ref);return old.producer.step_id===target.step_id&&old.producer.execution_revision===target.execution_revision;
      })))affected.add(node.id);
  }
  for(let changed=true;changed;){changed=false;for(const node of state.nodes)if(!affected.has(node.id)&&
    node.id!==newResult.producer.step_id&&node.depends_on.some(id=>affected.has(id))){affected.add(node.id);changed=true;}}
  for(const id of affected){
    const current=state.node_states[id];current.applicability='stale';current.stale_reason={
      affected_input_refs:clone(newResult.supersedes),new_result_ref:newResult.result_ref,reason:clone(newResult.recompute_reason)};
    current.wait_reason='model_revision_required';
    events.push({kind:'node_invalidated',step_id:id,old_action_id:current.execute_action_id,...clone(current.stale_reason)});
  }
}
function checkSize(state,limits){
  graphCapacity('graph_executions',state.executions.length,limits.maxExecutions);
  graphCapacity('graph_snapshot_bytes',Buffer.byteLength(JSON.stringify(state)),limits.snapshotBytes);
}
// Public text is model-authored. Drop common private path/credential forms;
// host source objects, workspace paths and checkpoint internals are never copied.
function safePublic(value){
  if(typeof value==='string')return value.replace(/(?:file|s3|gs):\/\/\S+|(?:\/(?:Users|home|tmp|private|var|workspace)\/)[^\s,;]*/g,'[private reference]')
    .replace(/(?:Bearer\s+|(?:api[_-]?key|token|password|secret)\s*[=:]\s*)[^\s,;]+/gi,'[protected]');
  if(Array.isArray(value))return value.map(safePublic);
  if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([key,child])=>[key,safePublic(child)]));
  return value;
}
/** Bounded current graph view. Histories are read through explicit result refs,
 * not a raw checkpoint dump. The host still owns authorized artifact access.
 */
export function projectEnterpriseGraph(state,limits){
  graphLimits(limits);requireCycle(state?.schema===GRAPH_SCHEMA,'Explicit graph v2 checkpoint required');
  const projection={schema:GRAPH_SCHEMA,graph_ref:state.graph_ref,graph_revision:state.graph_revision,
    goal:state.goal,output_mode:state.output_mode,model_revision_reason:state.revision_reason,
    nodes:state.nodes.map(node=>({...clone(node),...clone(state.node_states[node.id]),
      // Native settlement is distinct from the workflow phase/model assessment.
      // Preserve it after record/assess and derive it again on checkpoint replay.
      settled_status:executionFor(state,node.id,state.node_states[node.id].execution_revision)?.settled_status??null})),
    actions:state.actions.filter(action=>{const current=state.node_states[action.step_id];return action.kind==='execute'?
      current.execute_action_id===action.id&&['executing','executed'].includes(current.phase):
      current.assess_action_id===action.id&&['recorded','assessing'].includes(current.phase);}).map(clone),
    results:state.results.map(result=>resultView(result,limits))};
  const bounded=safePublic(projection);graphCapacity('graph_public_bytes',Buffer.byteLength(JSON.stringify(bounded)),limits.publicBytes);return bounded;
}
const selectFields=(value,fields)=>Object.fromEntries(fields.filter(key=>Object.hasOwn(value,key)).map(key=>[key,clone(value[key])]));
/** Approved public result fields, shared by graph snapshots, events and resolve.
 * Owner and future private manifest extensions cannot enter this projection.
 * An independently checked resultBytes budget defaults to publicBytes.
 */
function resultView(result,limits){
  const projection=selectFields(result,['schema','result_ref','slot','kind','consumed_results','observation_refs','artifact_refs',
    'summary','scope','supersedes','recompute_reason','input_limitations']);
  projection.producer=selectFields(result.producer,['step_id','action_id','definition_ref','execution_revision','attempt_id']);
  projection.source_versions=result.source_versions.map(version=>selectFields(version,['ref','revision']));
  projection.method=selectFields(result.method,['ref','revision','parameters_sha256','environment_ref','environment_unavailable','unavailable']);
  const bounded=safePublic(projection);
  graphCapacity('graph_public_result_bytes',Buffer.byteLength(JSON.stringify(bounded)),limits.resultBytes??limits.publicBytes);
  return bounded;
}
/** PRIVATE HOST CONTRACT: return an exact detached immutable manifest from the
 * protected checkpoint, bounded independently by resultBytes (or publicBytes).
 * Never register this function as a model/public tool or serialize its return
 * into public events. Public callers use operation=resolve and its result view.
 */
export function resolveEnterpriseGraphResultForHost(state,resultRef,limits){
  graphLimits(limits);requireCycle(state?.schema===GRAPH_SCHEMA,'Explicit graph v2 checkpoint required');
  const result=requireResult(state,resultRef);
  graphCapacity('graph_private_result_bytes',Buffer.byteLength(JSON.stringify(result)),limits.resultBytes??limits.publicBytes);
  return clone(result);
}

/** Returns {state,graph,actions,ready_nodes,events,result?}. state is PRIVATE host
 * checkpoint data. result is an approved bounded PUBLIC view, never a private
 * manifest; exact host reads use resolveEnterpriseGraphResultForHost.
 * No I/O, scheduling,
 * clock, implicit new work, hidden edge, or global pending_action exists here.
 */
export function reduceEnterpriseGraph(previous,operation,payload,host,limits){
  const command=validateGraphOperation(operation,payload,limits,previous?.work_edition??host?.graph_work_edition),events=[];
  let state=previous===null?null:clone(previous);
  requireCycle(!state||state.schema===GRAPH_SCHEMA,'Explicit graph v2 checkpoint required');
  const context=hostContext(host,state);
  if(operation==='plan'){
    requireCycle(!state,'Graph is already planned; use an explicit revision');
    const available=new Set(context.sources.map(item=>item.ref));
    requireCycle(unique(command.source_refs)&&command.source_refs.every(ref=>available.has(ref)),'Original source was not admitted');
    state={schema:GRAPH_SCHEMA,owner:context.owner,attempt_id:context.attempt_id,goal:command.goal,output_mode:command.output_mode,
      source_refs:clone(command.source_refs),source_versions:context.sources.filter(item=>command.source_refs.includes(item.ref)&&item.revision!==null)
        .map(item=>({ref:item.ref,revision:item.revision})),graph_revision:1,graph_ref:null,revision_reason:null,
      nodes:clone(command.nodes),node_states:{},actions:[],executions:[],results:[],external_results:[],revisions:[],history:[],
      ...(context.allow_selected_limited_inputs===true?{selected_limited_inputs:true}:{}),
      ...(context.graph_work_edition?{work_edition:context.graph_work_edition}:{}),...(context.work_envelope?{work_envelope:clone(context.work_envelope)}:{})};
    admitResults(state,context,limits);validateGraph(state,state.nodes,context);
    state.node_states=Object.fromEntries(state.nodes.map(node=>[node.id,emptyNode(state,node,1,null,context.sources)]));
    for(const node of state.nodes)selectTargets(state,node.id);
    events.push(graphCommit(state,null));
  }else{
    requireCycle(state,'Plan must be committed before graph operations');admitResults(state,context,limits);
    if(operation==='revise'){
      if(context.incremental_source_selection===true){
        // The host owns available grants. A task selects its own inputs; the
        // first batch does not freeze the source catalog for later batches.
        const selected=[...new Set(command.nodes.flatMap(node=>node.source_refs))];
        const added=selected.filter(ref=>!state.source_refs.includes(ref));
        requireCycle(added.every(ref=>context.sources.some(source=>source.ref===ref)),'Original source was not admitted');
        state.source_refs.push(...added);
        state.source_versions.push(...context.sources.filter(source=>added.includes(source.ref)&&source.revision!==null)
          .map(({ref,revision})=>({ref,revision})));
      }
      validateGraph(state,command.nodes,context);requireCycle(unique(command.rerun.map(item=>item.step_id)),'Duplicate recomputation request');
      const reruns=new Map(command.rerun.map(item=>[item.step_id,item]));
      for(const previousNode of state.nodes){
        const replacement=command.nodes.find(item=>item.id===previousNode.id),current=state.node_states[previousNode.id];
        requireCycle(replacement,'Graph revision cannot remove declared nodes');
        if(current.execute_action_id)requireCycle(same(previousNode,replacement)||reruns.has(previousNode.id),
          'Started node definition is immutable without explicit settled rerun');
      }
      for(const request of command.rerun){
        nodeFor(state,request.step_id);const current=state.node_states[request.step_id];
        requireCycle(current.execute_action_id&&settled.has(current.phase),'Recomputation requires a settled prior execution');
        requireCycle(executionFor(state,request.step_id,current.execution_revision).settled_status!=='unknown',
          'Unknown native outcome requires host reconciliation before another execution');
        const admitted=new Set([...context.sources.map(item=>item.ref),...state.source_refs,...state.results.map(item=>item.result_ref),
          ...state.external_results.map(item=>item.result_ref),...context.receipts.filter(item=>!item.owner||same(item.owner,state.owner)).map(item=>item.ref)]);
        requireCycle(request.reason.refs.every(ref=>admitted.has(ref)),'Recompute reason references were not admitted');
        requireCycle(request.reason.kind==='missing_result'?nonempty(request.reason.diagnostic):request.reason.refs.length>0,
          'Recompute needs an observed change, discrepancy or missing-result diagnostic');
        requireCycle(unique(request.supersedes)&&request.supersedes.every(ref=>{
          const result=requireResult(state,ref);return result.producer.step_id===request.step_id;
        }),'Supersession must name retained results of this producer');
      }
      state.nodes=clone(command.nodes);state.graph_revision++;
      for(const node of state.nodes){
        const current=Object.hasOwn(state.node_states,node.id)?state.node_states[node.id]:null,rerun=reruns.get(node.id);
        if(!current||!current.execute_action_id||rerun)state.node_states[node.id]=emptyNode(state,node,rerun?current.execution_revision+1:current?.execution_revision??1,rerun,context.sources);
      }
      for(const node of state.nodes)if(!state.node_states[node.id].execute_action_id)selectTargets(state,node.id);
      events.push(graphCommit(state,command.reason));
    }else if(operation==='start'){
      const node=nodeFor(state,command.step_id),current=state.node_states[node.id];
      if(command.kind==='assess'){
        requireCycle(['recorded','assessing'].includes(current.phase),'Assessment requires recorded work');
        if(current.phase==='recorded'){current.phase='assessing';executionFor(state,node.id,current.execution_revision).phase='assessing';}
      }else if(current.execute_action_id){
        requireCycle(current.phase==='executing','Node already started; a model revision is required for another execution');
      }else{
        refresh(state);requireCycle(current.applicability==='current'&&current.phase==='ready','Node is not ready; dependencies or model revision required');
        current.input_bindings=bindInputs(state,node,current);const action=issueAction(state,node,current,'execute');
        current.execute_action_id=action.id;current.phase='executing';current.wait_reason=null;
        state.executions.push({step_id:node.id,execution_revision:current.execution_revision,definition_ref:current.definition_ref,
          definition:clone(node),graph_ref:state.graph_ref,graph_revision:state.graph_revision,attempt_id:state.attempt_id,
          execute_action_id:action.id,assess_action_id:null,input_bindings:clone(current.input_bindings),output_bindings:[],phase:'executing',
          settled_status:null,record:null,assessment:null,recompute_reason:clone(current.recompute_reason),supersedes:clone(current.supersedes)});
        events.push({kind:'node_started',step_id:node.id,action_id:action.id,execution_revision:current.execution_revision,
          graph_ref:state.graph_ref,input_bindings:clone(current.input_bindings),settled_status:null});
      }
    }else if(operation==='execution_settled'){
      const {action,current,execution}=activeAction(state,command.action_id,'execute');
      if(execution.settled_status!==null)requireCycle(execution.settled_status===command.status,'Conflicting execution retry');
      else{
        requireCycle(current.phase==='executing','Only running execution can settle');execution.settled_status=command.status;
        current.phase=execution.phase='executed';
        events.push({kind:'node_execution_settled',step_id:action.step_id,action_id:action.id,
          execution_revision:action.execution_revision,graph_ref:action.graph_ref,settled_status:command.status});
      }
    }else if(operation==='record'){
      const {action,current,node,execution}=activeAction(state,command.action_id,'execute');
      if(execution.record)requireCycle(same(execution.record,command),'Conflicting record retry');
      else{
        const list=values=>({values:values.slice(0,limits.maxItems),total:values.length,omitted:Math.max(0,values.length-limits.maxItems)});
        const check=(condition,message,diagnostic)=>{
          try{requireCycle(condition,message);}catch(error){
            error.diagnostic={operation:'record',action_id:action.id,...diagnostic()};throw error;
          }
        };
        const declared=()=>list(node.outputs.map(({slot,kind})=>({slot,kind})));
        requireCycle(current.phase==='executed'&&execution.settled_status!==null,'Execution must settle before recording');
        requireCycle(command.outcome!=='completed'||execution.settled_status==='completed','Completed record requires completed execution');
        requireCycle(command.outcome==='completed'||command.limitations.length>0,'Limited or failed work needs explicit limitations');
        check(unique(command.outputs.map(item=>item.slot)),'Duplicate recorded output slot',()=>{
          const index=command.outputs.findIndex((item,index)=>command.outputs.findIndex(other=>other.slot===item.slot)<index);
          const slot=node.outputs.find(item=>item.slot===command.outputs[index].slot);
          return {code:'duplicate_output_slot',field:`outputs[${index}].slot`,output_index:index,...(slot?{slot:slot.slot}:{}),declared_slots:declared()};
        });
        check(command.outcome!=='completed'||command.outputs.length===node.outputs.length&&
          node.outputs.every(slot=>command.outputs.some(output=>output.slot===slot.slot)),
          'Completed record requires all declared output slots',()=>({code:'missing_output_slots',field:'outputs',declared_slots:declared(),
            missing_slots:list(node.outputs.filter(slot=>!command.outputs.some(output=>output.slot===slot.slot)).map(item=>item.slot))}));
        const {receipts,products}=admittedForAction(context,action);
        const inherited=current.input_bindings.map(binding=>requireResult(state,binding.result_ref));
        const observed=new Set([...receipts.filter(item=>item.status==='completed').map(item=>item.ref),
          ...inherited.flatMap(result=>result.observation_refs)]);
        const artifacts=new Set([...products.map(item=>item.ref),...inherited.flatMap(result=>result.artifact_refs)]);
        requireCycle(command.outcome!=='completed'||receipts.some(item=>item.status==='completed')||
          node.mode==='synthesis'&&current.input_bindings.length>0&&command.outputs.length>0,'Completed work needs an actual receipt or selected-result synthesis');
        const computation=computationContext(state,context,action,current.input_bindings,limits);
        const validRefs=()=>({observation_refs:list([...observed]),artifact_refs:list([...artifacts])});
        for(const [index,output] of command.outputs.entries()){
          const slot=node.outputs.find(item=>item.slot===output.slot);
          check(slot,'Output slot was not declared',()=>({code:'undeclared_output_slot',field:`outputs[${index}].slot`,output_index:index,declared_slots:declared()}));
          check(unique(output.observation_refs)&&unique(output.artifact_refs)&&output.observation_refs.every(ref=>observed.has(ref))&&
            output.artifact_refs.every(ref=>artifacts.has(ref)),'Output observation or artifact was not admitted for this action',()=>{
              const field=!unique(output.observation_refs)?'observation_refs':!unique(output.artifact_refs)?'artifact_refs':
                !output.observation_refs.every(ref=>observed.has(ref))?'observation_refs':'artifact_refs';
              return {code:unique(output[field])?'unadmitted_reference':'duplicate_reference',field:`outputs[${index}].${field}`,
                output_index:index,slot:slot.slot,valid_refs:validRefs()};
            });
          check(slot.kind==='artifact'?output.artifact_refs.length>0:output.observation_refs.length>0,'Output needs admitted content of its declared kind',
            ()=>({code:'missing_kind_content',field:`outputs[${index}].${slot.kind==='artifact'?'artifact_refs':'observation_refs'}`,output_index:index,slot:slot.slot,valid_refs:validRefs()}));
          const result={schema:RESULT_SCHEMA,owner:clone(state.owner),producer:{step_id:node.id,action_id:action.id,
            definition_ref:current.definition_ref,execution_revision:current.execution_revision,attempt_id:state.attempt_id},slot:output.slot,kind:slot.kind,
            ...clone(computation),consumed_results:current.input_bindings.map(item=>item.result_ref),observation_refs:clone(output.observation_refs),
            artifact_refs:clone(output.artifact_refs),summary:output.summary,scope:output.scope,
            supersedes:current.supersedes.filter(ref=>requireResult(state,ref).slot===output.slot),recompute_reason:clone(current.recompute_reason)};
          if(state.work_edition||state.selected_limited_inputs){
            const inheritedLimits=current.input_bindings.flatMap(binding=>[...(binding.accepted_limitations?[binding.accepted_limitations]:[]),
              ...(requireResult(state,binding.result_ref).input_limitations??[])]);
            if(inheritedLimits.length){
              result.input_limitations=[...new Map(inheritedLimits.map(item=>[item.result_ref+'\0'+item.assessment_ref,clone(item)])).values()];
              graphCapacity('graph_items',result.input_limitations.length,limits.maxItems);
            }
          }
          result.result_ref=reference('result',{producer:result.producer,slot:result.slot,owner:state.owner});
          requireCycle(!resultFor(state,result.result_ref),'Result identity already exists');state.results.push(result);
          const binding={slot:output.slot,kind:slot.kind,result_ref:result.result_ref};current.output_bindings.push(binding);execution.output_bindings.push(clone(binding));
          events.push({kind:'node_output_committed',step_id:node.id,action_id:action.id,slot:output.slot,result_ref:result.result_ref,result:resultView(result,limits)});
          markStale(state,result,events);
        }
        execution.record=clone(command);execution.admitted_observations=[...observed];execution.successful_receipts=receipts.filter(item=>item.status==='completed').map(item=>item.ref);
        current.phase=execution.phase='recorded';const assess=issueAction(state,node,current,'assess');
        current.assess_action_id=execution.assess_action_id=assess.id;
      }
    }else if(operation==='assess'){
      const {action,current,node,execution}=activeAction(state,command.action_id,'assess');
      if(execution.assessment)requireCycle(same(execution.assessment,command),'Conflicting assessment retry');
      else{
        requireCycle(['recorded','assessing'].includes(current.phase),'Assessment requires recorded execution');
        requireCycle(unique(command.checks.map(item=>item.description))&&command.checks.every(item=>node.checks.includes(item.description)),
          'Assessment checks must copy declared labels exactly');
        for(const check of command.checks){
          requireCycle(unique(check.refs)&&check.refs.every(ref=>execution.admitted_observations.includes(ref)),'Assessment reference was not admitted');
          requireCycle(check.status!=='passed'||check.refs.length>0,'Passed check needs actual admitted observations');
        }
        if(command.outcome==='success'){
          requireCycle(execution.record.outcome==='completed','Successful assessment needs completed work');
          requireCycle(node.outputs.every(slot=>current.output_bindings.some(binding=>binding.slot===slot.slot)),'Successful assessment requires all declared persisted outputs');
          requireCycle(node.checks.every(description=>command.checks.some(check=>check.description===description&&check.status==='passed')),
            'Successful assessment requires every declared check passed');
        }
        execution.assessment=clone(command);current.phase=execution.phase=command.outcome;
        if(state.work_edition||state.selected_limited_inputs)current.assessment_ref=execution.assessment_ref=reference('assessment',{action_id:action.id,assessment:command,limitations:execution.record.limitations});
        events.push({kind:'node_settled',step_id:node.id,action_id:execution.execute_action_id,assess_action_id:action.id,
          outcome:command.outcome,settled_status:execution.settled_status,actual_summary:command.summary,
          output_refs:current.output_bindings.map(item=>item.result_ref)});
      }
    }else if(operation==='resolve')requireResult(state,command.result_ref);
  }
  refresh(state);checkSize(state,limits);
  // A no-op retry does not grow retained history. Histories append only; no
  // settled execution record or result manifest is rewritten by a revision.
  if(!previous||!same(state,previous))state.history.push({operation,payload_digest:digest(command),graph_ref:state.graph_ref,
    action_id:command.action_id??null,events:clone(events)});
  checkSize(state,limits);
  const graph=projectEnterpriseGraph(state,limits);
  return {state,graph,actions:clone(graph.actions),ready_nodes:state.nodes.filter(node=>state.node_states[node.id].phase==='ready'&&
    state.node_states[node.id].applicability==='current').map(clone),events:safePublic(events),
    ...(operation==='resolve'?{result:resultView(requireResult(state,command.result_ref),limits)}:{})};
}
