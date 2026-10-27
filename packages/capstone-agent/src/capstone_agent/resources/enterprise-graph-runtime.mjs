/** Application adapter over the existing protected Research ledger. No model
 * calls, authority access, business phases, or alternative event store.
 *
 * resolveInputs(action,{signal}) returns {manifests,handles}. manifests must be
 * the exact selected protected result versions. Each bounded handle has an
 * opaque ref/result_ref and immutable:true, read_only:true; the host grants and
 * physically enforces that access. No writable parent path is an input grant.
 * dispatchNode({action,node,inputs,checkpoint},{signal}) returns a TRUSTED HOST
 * proposal {status,receipts,products,output,computation?}. Native receipts and
 * inspected products must match the exact lease owner/Attempt/action. Children
 * cannot invoke this port or mint admission from their text. inspectProducts
 * revalidates supplied product versions before admission; {ready,products} must
 * retain their exact immutable refs and action binding. output is private,
 * bounded proposal text, never an automatically accepted result or evidence.
 */
import {createHash} from 'node:crypto';
import {EnterpriseCycleError,requireCycle} from './enterprise-cycle-contract.mjs';
import {GRAPH_WORK_EDITION,graphOperationParameters,validateGraphOperation,graphLimits,graphCapacity} from './enterprise-graph-contract.mjs';
import {reduceEnterpriseGraph,projectEnterpriseGraph,graphAction,resolveEnterpriseGraphResultForHost} from './enterprise-graph-state.mjs';
import {createTaskGoal,reviewTaskGoal,validateTaskGoalFinish,taskRequirementSchema,taskGoalReviewSchema} from './task-goal-state.mjs';
import {runtimeLimits as resolveRuntimeLimits,checkCapacity,CapacityExceeded} from './runtime-limits.mjs';
import {taskTurnGuidance} from './task-turn-guidance.mjs';

export const GRAPH_CHECKPOINT_SCHEMA='capstone-enterprise-graph-checkpoint/1';
const operations=['plan','start','record','assess','revise','resolve'];
const names=Object.fromEntries(operations.map(op=>[op,'agent_research_'+op]));
const operationDescriptions={
  plan:'Declare the model-owned goal, nodes, dependencies, checks, selected sources, input bindings and output slots. This commits a plan, not recorded findings. The host schedules ready delegated nodes. Native read/bash/write work requires an explicitly started parent execute action.',
  start:'Start an exact declared step_id with kind execute or assess. Use execute for a ready parent node before any native tools; delegated execution is started by the host scheduler. Use assess only for recorded work. Copy the issued execute_action_id or assess_action_id from current graph state for subsequent operations.',
  record:'Record actual execution findings before resolving them or finishing delivery. For a validated structured producer proposal, copy its proposal_ref and issued execute_action_id instead of rebuilding outputs; choose exactly one proposal_ref or explicit outputs. Your outcome and limitations remain explicit parent judgment. Otherwise inspect exact named refs with agent_research_read section reference before mapping files to slots; several artifacts may fill a slot. Never bind by list order. For parent work, wait for its native tools to finish; this operation settles that action. Fill declared output slots with observation_refs and inspected artifact_refs, actual summary/scope and limitations. Use the actual completed, limited or failed outcome. The reply supplies immutable output result refs and an assess_action_id. Native return or host drain alone does not record outputs.',
  assess:'Assess recorded work using its exact issued assess_action_id. A validated proposal_ref may replace checks; this explicitly adopts producer check claims for your own judgment, never automatic host verification. Choose exactly one proposal_ref or explicit checks. Your outcome and summary are required. With explicit checks copy declared labels exactly and use passed, failed or not_run. Inspect needed retained refs with agent_research_read section reference; inspection creates no new evidence. Check refs must be admitted observation refs, not result or product refs. Success requires completed work, all declared persisted outputs and every required check passed with actual admitted observations. Use limited or failure for unmet checks. Current graph state and correction feedback supply authoritative labels and refs.',
  revise:'Revise the complete model-owned node set, including dependencies, input selection and definitions, with an explicit reason. The model decides graph changes and recomputation. To rerun settled work, supply step_id, a supported recompute reason and exact superseded result refs. A revision does not turn prior native proposals into recorded results.',
  resolve:'Read a public view of an exact result_ref copied from recorded output_bindings. Results exist only after record; action IDs, native proposal/observation/product refs and private file handles are not result refs. If no result is recorded, use current overview/proposal data to record the settled producer with its issued execute_action_id first. This tool does not discover files or return private handles.',
};
const nativeStatuses=new Set(['completed','failed','cancelled','unknown']);
const settledPhases=new Set(['success','limited','failure']);
const clone=value=>structuredClone(value);
const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?
  Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
const hash=value=>createHash('sha256').update(typeof value==='string'?value:JSON.stringify(canonical(value))).digest('hex');
const same=(a,b)=>hash(a)===hash(b);
const opaque=value=>typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$/.test(value);
const viewJson=value=>Array.isArray(value)?'['+value.map(viewJson).join(', ')+']':value&&typeof value==='object'?
  '{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+': '+viewJson(value[key])).join(', ')+'}':JSON.stringify(value);
const freeze=value=>{if(value&&typeof value==='object'){for(const child of Object.values(value))freeze(child);Object.freeze(value);}return value;};
// Match the reducer's public text boundary for application-only delivery and
// native proposal summaries. Exact private proposal bytes remain unchanged.
const publicText=value=>typeof value==='string'?value.replace(/(?:file|s3|gs):\/\/\S+|(?:\/(?:Users|home|tmp|private|var|workspace)\/)[^\s,;]*/g,'[private reference]')
  .replace(/(?:Bearer\s+|(?:api[_-]?key|token|password|secret)\s*[=:]\s*)[^\s,;]+/gi,'[protected]'):
  Array.isArray(value)?value.map(publicText):value&&typeof value==='object'?Object.fromEntries(Object.entries(value).map(([key,child])=>[key,publicText(child)])):value;
const fail=(code,message)=>{throw new EnterpriseCycleError(code,message);};
const text={type:'string',minLength:1};
const ref={...text,maxLength:256,pattern:'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$'};
export const graphFinishToolParameters={type:'object',additionalProperties:false,
  required:['outcome','delivery_result_refs','delivery_product_refs','limitations','summary'],properties:{
    outcome:{type:'string',enum:['success','limited','failure']},delivery_result_refs:{type:'array',items:ref},
    delivery_product_refs:{type:'array',items:ref},limitations:{type:'array',items:text},summary:text}};
export const graphInspectToolParameters={type:'object',additionalProperties:false,required:['action_id','products'],properties:{
  action_id:ref,products:{type:'array',items:{type:'object',additionalProperties:false,required:['path','role'],properties:{
    path:{...text,maxLength:1024},role:{type:'string',enum:['primary','support','reproduction']}}}}}};
export const graphReferenceReadParameters={type:'object',additionalProperties:false,required:['section','action_id'],properties:{
  section:{const:'reference',type:'string'},action_id:ref,ref,mode:{type:'string',enum:['metadata','text']},
  offset_bytes:{type:'integer',minimum:0},length_bytes:{type:'integer',minimum:1}}};

export function createEnterpriseGraphController({config,readResearch,commitResearch,inspectProducts,onProgress=()=>{},dispatchNode,resolveInputs,readReferenceContent,prepareSources}){
  if(!opaque(config?.researchTaskId)||!opaque(config?.researchAttemptId)||!config?.researchOwner||
    ![readResearch,commitResearch,inspectProducts,onProgress,dispatchNode,resolveInputs].every(port=>typeof port==='function'))
    throw new TypeError('Graph runtime needs exact owner, Attempt, task and protected host ports');
  const limits=graphLimits(config.researchRuntime?.graphLimits??config.researchRuntime?.limits);
  const isolatedTasks=config.researchRuntime?.isolatedTaskExecution===true;
  const lightweightTasks=isolatedTasks&&config.researchRuntime?.lightweightTaskNodes===true;
  const advisoryReviews=lightweightTasks&&config.researchRuntime?.nodeReviewMode==='advisory';
  const goalDriven=config.researchRuntime?.goalDrivenExecution===true;
  let turnStartedAt=Date.now();
  const turnGuidance=()=>taskTurnGuidance(config.researchRuntime?.turnGuidance,turnStartedAt);
  if(goalDriven&&!isolatedTasks)throw new TypeError('Whole-goal execution requires independent task contexts');
  // JSON schemas reuse scalar fragments. Detach each occurrence before adding
  // field guidance: structuredClone preserves aliases across distinct fields.
  const workEdition=config.researchRuntime?.graphWorkEdition,parameters=JSON.parse(JSON.stringify(graphOperationParameters(workEdition)));
  if(lightweightTasks&&!advisoryReviews)parameters.record.properties.assessment={type:'object',additionalProperties:false,
    required:['outcome','summary'],properties:{outcome:{type:'string',enum:['success','limited','failure']},
      summary:{type:'string',minLength:1},checks:clone(parameters.assess.properties.checks)},
    description:advisoryReviews?'Optional diagnostic note only. Recording already settles the node; do not supply this field to approve or reject work.':
      'Prefer one submission: record the actual return and supply your assessment here. With proposal_ref omit checks to adopt producer check claims. Unchecked findings remain limited. The host supplies the issued assessment action; separate record and assessment receipts remain persisted.'};
  if(goalDriven){
    parameters.plan.properties.requirements={type:'array',minItems:1,maxItems:limits.maxItems,items:clone(taskRequirementSchema)};
    parameters.plan.required.push('requirements');
    parameters.assess=advisoryReviews
      ?{type:'object',additionalProperties:false,required:['goal_review'],properties:{goal_review:clone(taskGoalReviewSchema)}}
      :{type:'object',additionalProperties:false,properties:{...parameters.assess.properties,goal_review:clone(taskGoalReviewSchema)}};
  }
  if(isolatedTasks){
    for(const operation of ['plan','revise'])parameters[operation].properties.nodes.items.properties.execution.enum=['delegated'];
    for(const operation of ['plan','revise']){
      parameters[operation].properties.nodes.items.description='Every required node field must be present, including depends_on, inputs and source_refs. Use [] when there is no dependency, no accepted-result input or no raw source. Do not omit required arrays.';
      parameters[operation].properties.nodes.items.properties.depends_on.description='Required task dependency IDs. Use [] for an independent task, including the initial discovery task.';
      if(lightweightTasks){
        const schema=parameters[operation].properties.nodes.items;
        schema.properties.purpose.description='One cohesive analytical result or decision. Related questions sharing calculation and interpretation belong together; do not create a separate executor for every metric or subquestion. Keep unrelated concerns separate.';
        schema.properties.instruction.description='Only this task scope, selected inputs and useful returns. Do not paste the whole multi-outcome request into one analysis node. Preparation supplies only common facts needed to choose subsequent work, not all downstream analyses.';
        schema.required=schema.required.filter(key=>!['depends_on','inputs','checks','questions','expected_outputs'].includes(key));
        schema.properties.questions.description='Optional distinct questions. If omitted or empty, the host uses the declared task purpose.';
        schema.properties.expected_outputs.description='Optional reader-facing output descriptions. If omitted or empty, the host uses the declared output slots descriptions.';
        schema.properties.checks.description='Optional checks needed for an explicit user requirement or a concrete integration risk. Omitted means []. Do not create a quality certification inventory, numeric sampling quota or editorial gate for ordinary research.';
        schema.description='Declare the task and its exact selected inputs. Omitted dependencies, result inputs and checks mean empty arrays. Questions and expected outputs derive from purpose and declared outputs when omitted. source_refs is required: select exact granted refs, including previous products. Top-level sources do not grant child access.';
        schema.properties.source_refs.description='Required explicit file inputs for this task, including selected previous products. Copy exact refs from the granted catalog. A filename in instruction or a top-level source_refs entry does not select child inputs. Use [] only when this task needs no source files.';
        schema.properties.mode.description='execute investigates sources or performs new analysis; synthesis composes retained findings/products and uses context for necessary interpretation. Mode guides scope; source permissions come only from the host catalog.';
        schema.properties.depends_on.description='Explicit producer dependency IDs; omitted means []. Result inputs still require their producer dependency.';
      }
    }
    parameters.revise.properties.nodes.description='Submit only new tasks or changed unstarted tasks. Existing tasks omitted here are retained exactly by the host. Never reconstruct a started definition to append new work.';
    if(lightweightTasks){
      parameters.plan.required=parameters.plan.required.filter(key=>key!=='source_refs');
      parameters.plan.properties.source_refs.description='Optional legacy field, ignored for task grants. The host derives graph sources from the explicit source_refs of each task; do not duplicate the catalog here.';
    }
    parameters.start.properties.kind.enum=['assess'];parameters.start.required=['step_id','kind'];
  }
  const selectedWork=config.researchRuntime?.graphWork;
  let workEnvelope;
  if(workEdition){
    requireCycle(selectedWork?.schema===workEdition&&['off','usable_draft'].includes(selectedWork.mode),'Invalid accepted graph work policy');
    if(selectedWork.mode==='usable_draft'){
      const {target_seconds:target,integration_reserve_seconds:reserve,child_wrapup_seconds:wrap}=selectedWork;
      const origin=config.researchRuntime.graphWorkStartedAt;
      requireCycle([target,reserve,wrap].every(value=>Number.isSafeInteger(value)&&value>0)&&target>reserve+wrap&&
        Number.isFinite(origin)&&origin>0&&Number.isFinite(config.deadlineAt),'Graph work needs trusted origin and bounded deadlines');
      const end=Math.min(config.deadlineAt,origin+target*1000);
      workEnvelope={...clone(selectedWork),origin_at_ms:origin,soft_task_deadline_ms:end,
        finish_by_ms:end-reserve*1000,wrapup_at_ms:end-(reserve+wrap)*1000,policy_sha256:hash(selectedWork)};
    }
  }else requireCycle(selectedWork===undefined,'Graph work policy requires its accepted edition');
  const capacities=resolveRuntimeLimits(config.runtimeLimits,{mode:config.runtimeLimitMode});
  const concurrency=config.researchRuntime?.delegation?.concurrency??config.researchRuntime?.delegation?.maxConcurrency;
  if(!Number.isSafeInteger(concurrency)||concurrency<1)throw new TypeError('Graph concurrency must be explicit');
  const taskId=config.researchTaskId,owner=clone(config.researchOwner),attemptId=config.researchAttemptId;
  const prefix='runtime.checkpoint.'+hash(taskId).slice(0,20)+'.';
  const jobs=new Map(),tokens=new Set(),waiters=new Set(),background=new Set();
  // Only this live controller may launch an intent it just issued. Persisted
  // intents from another process have unknown outcomes until reconciliation.
  const ownedIntents=new Set();
  const proposals=new Map(),toolReceipts=new Map();
  const nativeProgress=new Set();
  const parentInputs=new Map(),parentResolutions=new Map();
  const referenceReads=new Set();
  const executeCheckpoints=new Map();
  // Session-local delivery tracking only. Exact proposal bytes stay in the
  // protected checkpoint and explicit full reads recover them after compaction.
  const deliveredProposalOutputs=new Set();
  let snapshot=null,receipts=[],products=[],commands=[],dispatches=[],computations=[],delivery=null,closing=null,organization=null;
  let checkpoint=null,pending=null,loaded=false,loading,writer=Promise.resolve(),pumping,closed=false,lastError;
  const sources=clone(config.researchSources??[]),grants=clone(config.researchResults??[]);
  const pulse=()=>{for(const resolve of waiters)resolve();waiters.clear();};
  const waitFor=(promise,signal)=>{
    if(!signal)return promise;
    signal.throwIfAborted();
    return new Promise((resolve,reject)=>{
      const abort=()=>reject(signal.reason);
      signal.addEventListener('abort',abort,{once:true});
      promise.then(resolve,reject).finally(()=>signal.removeEventListener('abort',abort));
    });
  };
  const admissionSignal=signal=>{
    signal?.throwIfAborted();
    const remaining=Math.min(config.deadlineAt??Infinity,Date.now()+capacities.tool_timeout_seconds*1000)-Date.now();
    if(remaining<=0)throw new DOMException('Graph host operation deadline exceeded','TimeoutError');
    const timeout=AbortSignal.timeout(Math.ceil(remaining));
    return signal?AbortSignal.any([signal,timeout]):timeout;
  };
  // Cancellation bounds the caller's wait, while writer retains the actual
  // operation until it settles. Never recover an actively committing request.
  const serial=(fn,signal)=>{const result=writer.then(()=>{signal?.throwIfAborted();return fn();});writer=result.catch(()=>{});return waitFor(result,signal);};
  const retainedReceipts=()=>appendUnique(receipts,[...toolReceipts.values()].map(item=>item.receipt));
  const host=(extra={})=>({owner,attempt_id:attemptId,sources,receipts:retainedReceipts(),products,results:grants,
    incremental_source_selection:lightweightTasks,
    allow_selected_limited_inputs:lightweightTasks,
    ...(workEdition?{graph_work_edition:workEdition}:{}),...(workEnvelope?{work_envelope:workEnvelope}:{}),...extra});
  let workStatusCache;
  const workStatus=()=>{
    const envelope=snapshot?.work_envelope??workEnvelope;if(!envelope)return undefined;
    const now=Date.now(),phase=now>=envelope.soft_task_deadline_ms?'close_now':now>=envelope.finish_by_ms?'integration':now>=envelope.wrapup_at_ms?'child_wrapup':'work';
    const key=(checkpoint?.ref??'planning')+':'+phase;
    if(workStatusCache?.key===key)return clone(workStatusCache.value);
    const value={...clone(envelope),remaining_seconds:Math.max(0,Math.ceil((envelope.soft_task_deadline_ms-now)/1000)),phase,
      instruction:'Use the remaining shared task window for an honest useful draft. The reserve belongs to parent acceptance, integration and explicit finish; do not launch expired child work or polish optional details.'};
    workStatusCache={key,value};return clone(value);
  };
  const checkBytes=(dimension,value,limit)=>graphCapacity(dimension,Buffer.byteLength(JSON.stringify(value)),limit);
  const runtimeCapacity=(dimension,actual,unit='bytes')=>{
    if(capacities[dimension]!==undefined)checkCapacity(capacities,dimension,actual,unit,'enterprise_graph_runtime');
  };
  const interruptDebug=error=>{
    if(error?.name==='TimeoutError'||error?.name==='AbortError')throw error;
    if(config.runtimeLimitMode==='debug'&&error.capacity&&config.researchRuntime?.lightweightTaskNodes!==true){
      if(error.capacity.mode==='debug')throw error;
      const detail=error.capacity;throw new CapacityExceeded({[detail.dimension]:detail.limit},detail.dimension,detail.actual,detail.unit,
        'enterprise_graph_runtime',{mode:'debug'});
    }
  };
  function publicState(){return snapshot?projectEnterpriseGraph(snapshot,limits):null;}
  function goalContext(graph=publicState()){
    return {basis:hash(graph),hard_deadline_reached:Number.isFinite(config.deadlineAt)&&Date.now()>=config.deadlineAt,
      results:(graph?.results??[]).flatMap(result=>{
        const node=graph.nodes.find(item=>item.id===result.producer.step_id);
        return node?.applicability==='current'&&node.output_bindings.some(binding=>binding.result_ref===result.result_ref)?
          [{...clone(result),phase:node.phase}]:[];
      })};
  }
  const goalError=error=>error?.code==='task_goal_invalid'?new EnterpriseCycleError(error.code,error.message):error;
  const organizationView=(value=organization,graph=publicState())=>value?{
    ...publicText(clone(value)),review_current:Boolean(value.review&&value.review.basis===goalContext(graph).basis)}:null;
  const semanticProgress=()=>hash({graph_ref:snapshot?.graph_ref,nodes:snapshot?.node_states,results:snapshot?.results.map(item=>item.result_ref),
    native:[...nativeProgress].sort(),delivery,closing:closing?.payload??null});
  function graphReferences(graph){
    if(!graph)return null;
    const lightweight=config.researchRuntime?.lightweightTaskNodes===true;
    const compactBindings=bindings=>bindings.map(binding=>Object.fromEntries(Object.entries(binding)
      .filter(([key])=>!['source_versions','method_ref'].includes(key)).map(([key,value])=>[key,clone(value)])));
    const compactAction=action=>Object.fromEntries(['id','kind','step_id','definition_ref','execution_revision','source_refs','input_bindings']
      .filter(key=>Object.hasOwn(action,key)).map(key=>[key,key==='input_bindings'?compactBindings(action[key]):clone(action[key])]));
    return {schema:graph.schema,graph_ref:graph.graph_ref,graph_revision:graph.graph_revision,
      ...(goalDriven?{goal:graph.goal,output_mode:graph.output_mode}:{}),
      nodes:graph.nodes.map(node=>Object.fromEntries(['id','phase','applicability','execution_revision',
        'execute_action_id','assess_action_id','assessment_ref','settled_status','blocked_by','wait_reason','source_refs','selected_source_versions','input_bindings','output_bindings']
        .filter(key=>Object.hasOwn(node,key)&&(!lightweight||key!=='selected_source_versions'))
        .map(key=>[key,lightweight&&key==='input_bindings'?compactBindings(node[key]):clone(node[key])]))),
      actions:lightweight?graph.actions.map(compactAction):clone(graph.actions),retained_result_count:graph.results.length,
      // Keep exact result-to-file associations after accepted proposals leave
      // the pending list. These are choices, never automatic delivery grants.
      ...(isolatedTasks?{current_results:graph.results.flatMap(result=>{
        const node=graph.nodes.find(item=>item.id===result.producer.step_id);
        if(node?.applicability!=='current'||!settledPhases.has(node.phase)||
          !node.output_bindings.some(binding=>binding.result_ref===result.result_ref))return [];
        return [{result_ref:result.result_ref,step_id:node.id,action_id:result.producer.action_id,
          phase:node.phase,slot:result.slot,kind:result.kind,artifact_refs:clone(result.artifact_refs),
          ...(goalDriven?{summary:result.summary,scope:result.scope}:{}),
          input_limitations:clone(result.input_limitations??[]),
          products:deliveryGrants({delivery_result_refs:[result.result_ref],delivery_product_refs:result.artifact_refs}).map(productView)}];
      })}:{}),
      // Keep the current assignment visible across tool batches and model turns.
      // Full future definitions and long methods remain behind graph_ref.
      action_contracts:graph.nodes.filter(node=>['executed','recorded','assessing'].includes(node.phase)||
        node.execution==='parent'&&['ready','executing'].includes(node.phase)).map(node=>({
          step_id:node.id,...Object.fromEntries(['purpose','questions','expected_outputs','outputs','checks']
            .map(key=>[key,clone(node[key])]))})),
      definitions:'Retained by graph_ref. Read overview only to recover exact declarations or unseen native proposals; resolve exact result refs for saved findings.'+
        (lightweight?' Repeated source-version and method lineage is omitted here and retained in the full graph bindings.':'')};
  }
  function resultReply(output,at=checkpoint){
    const value={...publicText(clone(output)),...(output.graph?{graph:graphReferences(output.graph)}:{}),
      ...(goalDriven?{organization:organizationView(output.organization??organization,output.graph??publicState())}:{}),checkpoint:clone(at)};
    checkBytes('graph_tool_result_bytes',value,limits.publicBytes);
    return {content:[{type:'text',text:JSON.stringify(value)}],details:{capability:'agent_research_graph',ok:true,result:value}};
  }
  function validatedProposal(action,node,handoff,admitted,inspected,{metadata=false,selected_paths=[],inspect_partial=false}={}){
    requireCycle(!inspect_partial||workEdition===GRAPH_WORK_EDITION,'Partial inspection requires the accepted graph work edition');
    const exact=(value,keys)=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join(',')===[...keys].sort().join(',');
    const check=(condition,code,field,message,context={})=>{
      if(condition)return;
      const error=new EnterpriseCycleError('invalid_enterprise_cycle',message);
      error.diagnostic={code,field,...context};throw error;
    };
    check(exact(handoff,['schema','binding','outputs','checks','limitations'])&&handoff.schema==='capstone-node-proposal/1',
      'proposal_schema','graph_proposal','Structured proposal schema is invalid');
    check(same(handoff.binding,{action_id:action.id,definition_ref:action.definition_ref,execution_revision:action.execution_revision,
      consumed_results:action.input_bindings.map(item=>item.result_ref),source_versions:action.source_versions}),
      'proposal_binding','binding','Structured proposal action or input version changed');
    const inherited=action.input_bindings.map(binding=>[...snapshot.results,...snapshot.external_results].find(result=>result.result_ref===binding.result_ref));
    const observations=new Set([...admitted.filter(item=>item.status==='completed').map(item=>item.ref),...inherited.flatMap(item=>item.observation_refs)]);
    const artifacts=new Set(metadata?selected_paths:[...inspected.map(item=>item.ref),...inherited.flatMap(item=>item.artifact_refs)]);
    check(Array.isArray(handoff.outputs)&&Array.isArray(handoff.checks)&&Array.isArray(handoff.limitations)&&handoff.limitations.every(item=>typeof item==='string'&&item.trim()),
      'proposal_arrays','graph_proposal','Structured proposal arrays are invalid');
    if(!inspect_partial)check(handoff.outputs.length===node.outputs.length&&new Set(handoff.outputs.map(item=>item?.slot)).size===handoff.outputs.length,
      'output_slots','outputs','Structured proposal must name each declared output slot exactly once');
    const artifactKey=metadata?'product_paths':'artifact_refs';
    const validOutputs=[],validChecks=[],diagnostics=[];
    const inspect=(fn,valid)=>{try{fn();valid();}catch(error){if(!inspect_partial||!error.diagnostic)throw error;diagnostics.push(clone(error.diagnostic));}};
    for(const output of handoff.outputs){
      const declared=node.outputs.find(item=>item.slot===output?.slot);
      inspect(()=>check(declared&&handoff.outputs.filter(item=>item?.slot===output.slot).length===1&&exact(output,['slot',artifactKey,'observation_refs','summary','scope'])&&
        [artifactKey,'observation_refs'].every(key=>Array.isArray(output[key])&&new Set(output[key]).size===output[key].length)&&
        output[artifactKey].every(ref=>artifacts.has(ref))&&output.observation_refs.every(ref=>observations.has(ref))&&
        ['summary','scope'].every(key=>typeof output[key]==='string'&&output[key].trim())&&
        (declared.kind==='artifact'?output[artifactKey].length>0:output.observation_refs.length>0),
        'output_support','outputs','Structured output needs its declared slot kind and exact admitted support',declared?{slot:declared.slot}:{}),()=>validOutputs.push(clone(output)));
    }
    if(!inspect_partial)check(handoff.checks.length===node.checks.length&&new Set(handoff.checks.map(item=>item?.description)).size===handoff.checks.length,
      'check_labels','checks','Structured proposal must name each declared check exactly once');
    for(const [index,item] of handoff.checks.entries()){
      inspect(()=>{
      const field='checks['+index+']',context={check_index:index,...(node.checks.includes(item?.description)?{check_label:item.description}:{}),
        ...(['passed','failed','not_run'].includes(item?.status)?{status:item.status}:{}),
        ...(Array.isArray(item?.refs)?{refs:item.refs.filter(ref=>observations.has(ref)),unsupported_ref_count:item.refs.filter(ref=>!observations.has(ref)).length}:{}),valid_refs:[...observations]};
      check(exact(item,['description','status','refs','explanation']),'check_shape',field,'Structured check fields are invalid',context);
      check(node.checks.includes(item.description),'check_label',field+'.description','Structured check must copy its declared label exactly',
        {...context,required_labels:clone(node.checks)});
      check(handoff.checks.filter(check=>check?.description===item.description).length===1,'check_labels',field+'.description','Structured check label must be unique',context);
      check(['passed','failed','not_run'].includes(item.status),'check_status',field+'.status','Structured check status is invalid',context);
      check(Array.isArray(item.refs)&&new Set(item.refs).size===item.refs.length&&item.refs.every(ref=>observations.has(ref)),
        'check_refs',field+'.refs','Structured check refs must be exact admitted observations',context);
      check(item.status!=='passed'||item.refs.length>0,'check_support_missing',field+'.refs','A passed check needs admitted observation support',context);
      check(typeof item.explanation==='string'&&item.explanation.trim(),'check_explanation',field+'.explanation','Structured check needs an actual explanation',context);
      },()=>validChecks.push(clone(item)));
    }
    checkBytes('graph_node_proposal_bytes',handoff,limits.resultBytes??limits.publicBytes);
    if(inspect_partial)return {status:'incomplete',outputs:validOutputs,checks:validChecks,limitations:clone(handoff.limitations),
      missing_slots:node.outputs.filter(item=>!validOutputs.some(output=>output.slot===item.slot)).map(item=>item.slot),
      missing_check_labels:node.checks.filter(label=>!validChecks.some(item=>item.description===label)),diagnostics,
      instruction:'These are individually validated associations, not a complete approved proposal. Parent must explicitly record limited outputs and assess actual limitations.'};
    if(metadata)return {status:'metadata_valid'}; // No sealed grant or admission is created here.
    return {...clone(handoff),proposal_ref:'proposal:'+hash({action,handoff}),status:'validated',checks_are:'producer claims; parent assessment required'};
  }
  function proposalPayload(operation,payload){
    if(payload.proposal_ref===undefined)return payload;
    const action=graphAction(snapshot,payload.action_id),node=snapshot.nodes.find(item=>item.id===action.step_id),current=snapshot.node_states[action.step_id];
    const proposal=dispatches.find(item=>item.action_id===current.execute_action_id)?.proposal;
    requireCycle(proposal?.status==='validated'&&proposal.proposal_ref===payload.proposal_ref&&current.applicability==='current'&&
      action.execution_revision===current.execution_revision&&action.definition_ref===current.definition_ref&&
      (operation==='record'?action.kind==='execute'&&current.phase==='executed':action.kind==='assess'&&['recorded','assessing'].includes(current.phase)),
      'Proposal ref must belong to this exact current action and execution');
    const producer=graphAction(snapshot,current.execute_action_id);
    validatedProposal(producer,node,{schema:proposal.schema,binding:proposal.binding,outputs:proposal.outputs,checks:proposal.checks,limitations:proposal.limitations},
      retainedReceipts().filter(item=>item.action_id===producer.id),products.filter(item=>item.action_id===producer.id));
    const {proposal_ref,...expanded}=payload;
    return {...expanded,[operation==='record'?'outputs':'checks']:clone(proposal[operation==='record'?'outputs':'checks'])};
  }
  function assessmentFeedback(operation,payload,error){
    if(operation!=='assess'||!(error instanceof EnterpriseCycleError)||!snapshot||pending||closed||closing||delivery)return;
    const action=snapshot.actions.find(item=>item.id===payload?.action_id&&item.kind==='assess');
    const current=action&&snapshot.node_states[action.step_id],node=action&&snapshot.nodes.find(item=>item.id===action.step_id);
    const execution=action&&snapshot.executions.find(item=>item.step_id===action.step_id&&item.execution_revision===action.execution_revision);
    if(!node||!execution||current?.assess_action_id!==action.id||current.execution_revision!==action.execution_revision||
      current.definition_ref!==action.definition_ref||current.applicability!=='current'||
      !['recorded','assessing'].includes(current.phase)||!execution.record||execution.assessment)return;
    const proposal=dispatches.find(item=>item.action_id===current.execute_action_id)?.proposal;
    if(payload.proposal_ref&&Object.hasOwn(payload,'checks')&&proposal?.status==='validated'&&proposal.proposal_ref===payload.proposal_ref)
      return {action_id:action.id,proposal_ref:proposal.proposal_ref,omit_fields:['checks'],
        instruction:'Use action_id, proposal_ref, outcome and summary only. Omit checks entirely. If you choose explicit checks instead, omit proposal_ref. Outcome and summary remain your judgment.'};
    const value=publicText({action_id:action.id,required_check_labels:clone(node.checks),
      valid_check_refs:clone(execution.admitted_observations),
      recorded_output_result_refs:execution.output_bindings.map(item=>item.result_ref)});
    if([value.required_check_labels,value.valid_check_refs,value.recorded_output_result_refs].some(items=>items.length>limits.maxItems))return;
    return value;
  }
  function errorReply(error,feedback,operation){
    lastError=error.code??'research_graph_rejected';
    const capacityRecovery=config.researchRuntime?.lightweightTaskNodes===true&&error.capacity&&!error.category;
    const rejected=capacityRecovery||error.category==='rejected'||error.definiteRejected||error instanceof EnterpriseCycleError&&error.code!=='research_update_not_confirmed';
    // Port failures must not leak host paths, raw proposals, or credentials.
    const message=publicText(capacityRecovery?'This operation exceeds its capacity. Retained task state remains available. Reduce this request, read a smaller page, or split the work. Do not retry unchanged input.':error.category==='rejected'?'The host definitively rejected this selection. Correct the declared selection or record an explicit limitation; replaying the same rejected request cannot change its outcome.':error instanceof EnterpriseCycleError?error.message:
      'The host operation is not confirmed. Recover the same request before more native work.');
    const reply={isError:true,content:[{type:'text',text:message}],details:{capability:'agent_research_graph',ok:false,error:{code:lastError,message,
      category:rejected?'rejected':'unknown',recovery:capacityRecovery?'reduce_or_split_request':rejected?'correct_selection':'recover_exact_request',
      ...(opaque(error.request_id)?{request_id:error.request_id}:{}),
      ...(opaque(error.action_id)?{action_id:error.action_id}:{}),
      ...(opaque(error.checkpoint?.ref)&&Number.isSafeInteger(error.checkpoint?.revision)?{checkpoint:clone(error.checkpoint)}:{}),
      ...(['freeze','resolve','read'].includes(error.operation)?{operation:error.operation}:{}),
      ...(['selection_invalid','action_unavailable','owner_invalid','source_unavailable','capacity_exceeded'].includes(error.rejection_code)?{rejection_code:error.rejection_code}:{}),
      ...(error.capacity?{capacity:error.capacity}:{})}}};
    if(error.category||capacityRecovery)reply.content[0].text=message+' '+JSON.stringify(reply.details.error);
    if(operation==='record'&&rejected&&error instanceof EnterpriseCycleError&&error.diagnostic?.operation==='record'&&
      ['duplicate_output_slot','missing_output_slots','undeclared_output_slot','unadmitted_reference','duplicate_reference','missing_kind_content'].includes(error.diagnostic.code)){
      // This is the pure reducer's rejected command context, not a fresh read
      // of a snapshot that may have moved while the operation was awaited.
      const diagnostic=publicText(clone(error.diagnostic));
      const lists=[diagnostic.declared_slots,diagnostic.missing_slots,diagnostic.valid_refs?.observation_refs,diagnostic.valid_refs?.artifact_refs].filter(Boolean);
      while(true){
        const hint=' Record correction context; values may be omitted as counted. Copy only needed admitted refs; choose the outcome yourself. '+JSON.stringify(diagnostic);
        const extended={...reply,content:[{type:'text',text:message+hint}],details:{...reply.details,error:{...reply.details.error,record_feedback:diagnostic}}};
        if(Buffer.byteLength(JSON.stringify(extended))<=limits.publicBytes)return extended;
        const remaining=lists.filter(list=>list.values.length).sort((a,b)=>Buffer.byteLength(JSON.stringify(b.values))-Buffer.byteLength(JSON.stringify(a.values)))[0];
        if(!remaining)break;
        remaining.values.pop();remaining.omitted=remaining.total-remaining.values.length;
      }
    }
    if(feedback){
      const hint=(feedback.omit_fields?' Correct the mutually exclusive assessment fields. ':
        ' Copy required_check_labels exactly. Use valid_check_refs for check evidence; recorded_output_result_refs identify saved outputs only. ')+JSON.stringify(feedback);
      const extended={...reply,content:[{type:'text',text:message+hint}],details:{...reply.details,error:{...reply.details.error,assessment_feedback:feedback}}};
      if(Buffer.byteLength(JSON.stringify(extended))<=limits.publicBytes)return extended;
    }
    return reply;
  }
  const stateData=()=>({snapshot:clone(snapshot),receipts:retainedReceipts(),products:clone(products),commands:clone(commands),
    dispatches:clone(dispatches),computations:clone(computations),delivery:clone(delivery),closing:clone(closing),
    ...(config.researchRuntime?.turnGuidance?{turn_guidance_started_at_ms:turnStartedAt}:{}),
    ...(goalDriven?{organization:clone(organization)}:{})});
  function retainExecuteCheckpoints(saved,at){
    const progress=saved.public_progress;
    if(saved.runId!==taskId||saved.committed_revision!==at.revision||
      at.ref!==prefix+hash('call:'+saved.command_id).slice(0,24)||!same(saved.snapshot?.owner,owner)||
      saved.snapshot?.attempt_id!==attemptId||!same(progress?.owner,owner)||progress?.attempt_id!==attemptId||progress?.task_id!==taskId)return;
    for(const published of progress.graph?.actions??[]){
      if(published.kind!=='execute')continue;
      const action=saved.snapshot.actions.find(item=>item.id===published.id);
      if(!action||!same(action,published)||!same(action.owner,owner)||action.attempt_id!==attemptId)continue;
      const prior=executeCheckpoints.get(action.id);
      if(!prior||prior.checkpoint.revision<at.revision)executeCheckpoints.set(action.id,freeze(clone({action,checkpoint:at})));
    }
  }
  function adopt(saved,at){
    const retained=saved.snapshot.work_envelope;
    requireCycle(saved.snapshot.work_edition===workEdition&&Boolean(retained)===Boolean(workEnvelope),
      'Accepted graph work edition or immutable envelope differs from checkpoint');
    if(retained){
      const derived=['origin_at_ms','soft_task_deadline_ms','finish_by_ms','wrapup_at_ms','policy_sha256'];
      const policy=Object.fromEntries(Object.entries(retained).filter(([key])=>!derived.includes(key)));
      requireCycle(same(policy,selectedWork)&&retained.policy_sha256===hash(selectedWork)&&
        derived.slice(0,4).every(key=>Number.isSafeInteger(retained[key]))&&retained.origin_at_ms>0&&
        retained.soft_task_deadline_ms>retained.origin_at_ms&&retained.soft_task_deadline_ms<=retained.origin_at_ms+selectedWork.target_seconds*1000&&
        retained.finish_by_ms===retained.soft_task_deadline_ms-selectedWork.integration_reserve_seconds*1000&&
        retained.wrapup_at_ms===retained.finish_by_ms-selectedWork.child_wrapup_seconds*1000,
        'Committed graph work envelope does not match its accepted policy');
      // A later process/continuation can have a later claim start. The already
      // committed host envelope owns this graph; restoration never renews it.
      workEnvelope=clone(retained);
    }
    retainExecuteCheckpoints(saved,at);
    if(Number.isFinite(saved.turn_guidance_started_at_ms)&&saved.turn_guidance_started_at_ms>0)
      turnStartedAt=saved.turn_guidance_started_at_ms;
    snapshot=clone(saved.snapshot);receipts=clone(saved.receipts);products=clone(saved.products);commands=clone(saved.commands);
    dispatches=clone(saved.dispatches);computations=clone(saved.computations??[]);delivery=clone(saved.delivery??null);
    closing=clone(saved.closing??null);checkpoint=clone(at);
    if(goalDriven){createTaskGoal(saved.organization?.requirements,limits);organization=clone(saved.organization);}
  }
  async function view(){
    const current=await readResearch();requireCycle(current&&Number.isSafeInteger(current.research_revision)&&current.research_revision>=0,
      'Protected research revision is invalid');return current;
  }
  function validateSaved(saved){
    requireCycle(saved.schema===GRAPH_CHECKPOINT_SCHEMA&&saved.runId===taskId&&same(saved.snapshot?.owner,owner)&&
      saved.snapshot?.attempt_id===attemptId&&opaque(saved.command_id)&&Number.isSafeInteger(saved.committed_revision)&&
      ['receipts','products','commands','dispatches'].every(key=>Array.isArray(saved[key])),'Protected graph checkpoint identity is invalid');
    projectEnterpriseGraph(saved.snapshot,limits);
  }
  async function acknowledge(){
    const retained=pending;requireCycle(retained,'No unconfirmed graph request');
    let response;
    try{response=await commitResearch(retained.requestId,clone(retained.request),retained.signal);}
    catch(error){lastError='research_update_not_confirmed';pulse();throw error;}
    const ack=response?.details?.result;
    if(response?.details?.ok!==true||ack?.status!=='committed'){
      if(ack?.status==='rejected'){pending=null;const error=new EnterpriseCycleError(ack.code??'research_update_rejected','Graph checkpoint was rejected. No execution was dispatched.');
        error.definiteRejected=true;pulse();throw error;}
      fail('research_update_not_confirmed','Recover the exact unconfirmed graph request before new work.');
    }
    requireCycle(ack.receipt?.research_revision===retained.saved.committed_revision,'Graph acknowledgement revision is invalid');
    adopt(retained.saved,{ref:retained.noteId,revision:ack.receipt.research_revision});pending=null;
    if(retained.saved.command_id.startsWith('settle-'))proposals.delete(retained.saved.public_progress.action_id);
    for(const [id,item]of toolReceipts)if(retained.saved.receipts.some(value=>same(value,item.receipt)))toolReceipts.delete(id);
    lastError=undefined;
    // Publication can occur only after confirmed CAS. A delivery sink failure
    // does not erase or repeat the already committed native action intent.
    try{await onProgress({...clone(retained.saved.public_progress),checkpoint:clone(checkpoint)});}
    catch{lastError='research_progress_delivery_failed';}
    pulse();return retained;
  }
  async function persist(commandId,data,events=[],actionId,signal,origin=commandId){
    signal?.throwIfAborted();requireCycle(!pending,'Recover the unconfirmed graph checkpoint first');
    const current=await view(),noteId=prefix+hash('call:'+commandId).slice(0,24);
    const previous=(current.state?.notes??[]).find(note=>note.note_id===noteId);
    if(previous){const saved=JSON.parse(previous.text);validateSaved(saved);
      // A retained operation may already have committed before siblings moved
      // the ledger. Its old snapshot must never replace the newer state.
      if(!checkpoint||checkpoint.revision<saved.committed_revision)adopt(saved,{ref:noteId,revision:saved.committed_revision});return;}
    const graph=projectEnterpriseGraph(data.snapshot,limits);
    const control=data.commands.find(command=>command.id===commandId);
    const public_progress={type:'enterprise_graph_progress',owner:clone(owner),attempt_id:attemptId,task_id:taskId,graph,
      events:clone(events),...(actionId?{action_id:actionId}:{}),
      ...(control?{control:{tool_call_id:commandId,tool_name:'agent_research_'+control.operation}}:{})};
    checkBytes('graph_progress_bytes',public_progress,limits.publicBytes);
    const wire={...public_progress,checkpoint:{ref:noteId,revision:current.research_revision+1}};
    checkBytes('graph_progress_envelope_bytes',wire,limits.publicBytes);
    runtimeCapacity('event_bytes',Buffer.byteLength(JSON.stringify(wire)+'\n'));
    const saved={schema:GRAPH_CHECKPOINT_SCHEMA,runId:taskId,command_id:commandId,committed_revision:current.research_revision+1,
      ...clone(data),public_progress};
    checkBytes('graph_checkpoint_bytes',saved,limits.snapshotBytes);
    runtimeCapacity('control_document_bytes',Buffer.byteLength(JSON.stringify(saved)));
    const note={note_id:noteId,text:JSON.stringify(saved),refs:[]};
    runtimeCapacity('research_text_chars',Array.from(note.text).length,'codepoints');
    const changes={notes:[note],...(!current.state?{goal:data.snapshot.goal}:{})};
    const requestId='runtime-'+hash(taskId+'\0call:'+commandId),request={expected_revision:current.research_revision,changes};
    runtimeCapacity('research_request_bytes',Buffer.byteLength(JSON.stringify({request_id:'request-'+hash(requestId),...request})+'\n'));
    const nextRevision=current.research_revision+1;
    const candidate={...current,research_revision:nextRevision,state:{...(current.state??{}),
      ...(!current.state?{goal:data.snapshot.goal,...(current.research_id?{research_id:current.research_id}:{})}:{}),
      claims:current.state?.claims??[],notes:[...(current.state?.notes??[]),note],revision:nextRevision}};
    runtimeCapacity('research_response_bytes',Buffer.byteLength(viewJson(candidate)+'\n'));
    runtimeCapacity('research_note_count',candidate.state.notes.length,'items');
    pending={saved,noteId,origin,signal,requestId,request};
    await acknowledge();
  }
  async function load(){
    if(loaded)return;if(loading)return loading;
    loading=(async()=>{
      const current=await view();
      const notes=(current.state?.notes??[]).filter(item=>item.note_id.startsWith(prefix));
      const candidates=notes.map(note=>({note,saved:JSON.parse(note.text)})).filter(item=>item.saved.schema===GRAPH_CHECKPOINT_SCHEMA);
      if(candidates.length){
        for(const {note,saved} of candidates)if(saved.committed_revision<=current.research_revision)
          retainExecuteCheckpoints(saved,{ref:note.note_id,revision:saved.committed_revision});
        const latest=candidates.sort((a,b)=>b.saved.committed_revision-a.saved.committed_revision)[0];
        // Checkpoints retain exact selected source identities and versions. Restore
        // their protected manifests before validation or scheduling any consumer.
        if(config.researchRuntime?.adaptiveAgentLoop===true){
          const refs=[...new Set((latest.saved.snapshot?.nodes??[]).flatMap(node=>node.source_refs??[]))];
          for(const source of await prepareSources?.(refs,{signal:admissionSignal()})??[]){
            const frozen=(latest.saved.snapshot?.actions??[]).flatMap(action=>action.source_versions??[])
              .filter(item=>item.ref===source.ref);
            requireCycle(frozen.every(item=>item.revision===source.revision),'Restored source version changed');
            const previous=sources.find(item=>item.ref===source.ref);
            requireCycle(!previous||hash(previous)===hash(source),'Source version changed');
            if(!previous)sources.push(clone(source));
          }
        }
        validateSaved(latest.saved);
        adopt(latest.saved,{ref:latest.note.note_id,revision:latest.saved.committed_revision});
        // No process-local child survives restore. Unknown remains explicit;
        // the native executor is never started from a saved executing lease.
        loaded=true;
        const interrupted=snapshot.executions.filter(item=>item.phase==='executing');
        if(interrupted.length){
          const data=stateData(),events=[],ids=new Set(interrupted.map(item=>item.execute_action_id));
          for(const execution of interrupted){
            const result=reduceEnterpriseGraph(data.snapshot,'execution_settled',
              {action_id:execution.execute_action_id,status:'unknown'},host(),limits);
            data.snapshot=result.state;events.push(...result.events);
          }
          data.dispatches=data.dispatches.map(item=>ids.has(item.action_id)?{...item,status:'unknown'}:item);
          // One atomic recovery checkpoint accounts for every interrupted lease,
          // even if its acknowledgement is lost before the controller resumes.
          await serial(()=>persist('restore-'+hash([...ids].sort()).slice(0,32),data,events));
        }
      }
      loaded=true;
    })();
    try{await loading;}finally{loading=undefined;}
  }
  function commandReceipt(id,operation,payload){
    const old=commands.find(item=>item.id===id);
    if(old)requireCycle(old.operation===operation&&old.payload_hash===hash(payload),'A command ID cannot change its operation or payload');
    return old;
  }
  function checkedAdmission(item,action,product=false){
    requireCycle(item&&opaque(item.ref)&&same(item.owner,owner)&&item.action_id===action.id&&item.attempt_id===attemptId&&
      (product?item.status==='ready':nativeStatuses.has(item.status)),'Native admission does not match its exact action lease');
    if(product)requireCycle(typeof item.path==='string'&&item.path.length>0&&!item.path.startsWith('/')&&!item.path.includes('\\')&&
      item.path.split('/').every(part=>part&&part!=='.'&&part!=='..')&&!/[\x00-\x1f]/.test(item.path)&&
      /^[a-f0-9]{64}$/.test(item.sha256)&&Number.isSafeInteger(item.bytes)&&item.bytes>0,
      'An inspected product needs a safe relative path and exact nonempty byte identity');
    if(product)requireCycle(Array.isArray(item.roles)&&item.roles.length>0&&new Set(item.roles).size===item.roles.length&&
      item.roles.every(role=>['primary','support','reproduction'].includes(role)),
      'Inspected products need unique published presentation roles');
    return clone(item);
  }
  function appendUnique(items,values){
    const result=clone(items);for(const value of values){
      const prior=result.find(item=>item.ref===value.ref&&item.action_id===value.action_id&&item.attempt_id===value.attempt_id);
      requireCycle(!prior||same(prior,value),'An immutable native receipt or product changed');if(!prior)result.push(clone(value));}
    for(const item of result.filter(item=>item.status==='ready')){
      const versions=result.filter(other=>other.ref===item.ref);
      requireCycle(versions.every(other=>same(other.owner,item.owner)&&other.path===item.path&&other.sha256===item.sha256&&other.bytes===item.bytes),
        'An immutable artifact ref changed its owner or byte identity across action grants');
    }
    graphCapacity('graph_admissions',result.length,limits.maxItems);return result;
  }
  async function inspectVersions(action,candidates,signal){
    if(!candidates.length)return [];
    const supplied=candidates.map(item=>checkedAdmission(item,action,true));
    const observed=await inspectProducts({snapshot:clone(snapshot),action:clone(action),products:clone(supplied),productRefs:supplied.map(item=>item.ref)},{signal});
    requireCycle(observed?.ready===true&&Array.isArray(observed.products),'Product inspection did not confirm the exact versions');
    const inspected=observed.products.map(item=>checkedAdmission(item,action,true));
    requireCycle(inspected.length===supplied.length&&supplied.every(item=>inspected.some(other=>same(item,other))),
      'Product inspection changed or omitted the proposed immutable version');return inspected;
  }
  async function inputContext(action,signal){
    const resolved=await resolveInputs(freeze(clone(action)),{signal});
    requireCycle(resolved&&Object.keys(resolved).sort().join(',')==='handles,manifests'&&Array.isArray(resolved.manifests)&&Array.isArray(resolved.handles),
      'Input resolution requires exact manifests and immutable handles');
    const refs=action.input_bindings.map(item=>item.result_ref);
    requireCycle(resolved.manifests.length===refs.length&&new Set(resolved.manifests.map(item=>item.result_ref)).size===refs.length&&
      resolved.manifests.every(item=>refs.includes(item.result_ref)&&same(item,resolveEnterpriseGraphResultForHost(snapshot,item.result_ref,limits))),
      'Resolved input manifest differs from its protected selected version');
    requireCycle(resolved.handles.every(item=>item&&refs.includes(item.result_ref)&&opaque(item.ref)&&item.immutable===true&&item.read_only===true),
      'Input handles must grant immutable read-only selected versions');
    graphCapacity('graph_input_handles',resolved.handles.length,limits.maxItems);
    checkBytes('graph_private_input_bytes',resolved,limits.resultBytes??limits.publicBytes);
    return freeze(clone(resolved));
  }
  function currentExecute(actionId){
    const action=graphAction(snapshot,actionId),current=snapshot.node_states[action.step_id];
    requireCycle(action.kind==='execute'&&same(action.owner,owner)&&action.attempt_id===attemptId&&
      current.execute_action_id===action.id&&current.execution_revision===action.execution_revision&&
      current.definition_ref===action.definition_ref&&current.applicability==='current','Inspection requires an exact current execute action');
    return action;
  }
  function activeParent(){
    if(!snapshot||closed||closing||delivery)return null;
    const nodes=snapshot.nodes.filter(node=>node.execution==='parent'&&snapshot.node_states[node.id].phase==='executing');
    requireCycle(nodes.length<=1,'Only one parent execute action may own inputs');
    return nodes.length?currentExecute(snapshot.node_states[nodes[0].id].execute_action_id):null;
  }
  const productView=item=>({ref:item.ref,kind:'product',logical_path:item.path,sha256:item.sha256,bytes:item.bytes,roles:clone(item.roles)});
  async function readReference(callId,payload,{signal,onBinding}={}){
    const abort=new AbortController();referenceReads.add(abort);
    try{
      signal=admissionSignal(signal);signal=AbortSignal.any([signal,abort.signal]);await recoverPending({signal});await waitFor(writer,signal);
      requireCycle(payload&&Object.keys(payload).every(key=>['section','action_id','ref','mode','offset_bytes','length_bytes'].includes(key))&&
        payload.section==='reference'&&opaque(payload.action_id)&&(!Object.hasOwn(payload,'ref')||opaque(payload.ref)), 'Invalid exact reference inspection');
      requireCycle(!pending&&!closed&&!closing&&!delivery,'Reference inspection is blocked by closing or unconfirmed state');
      const action=currentExecute(payload.action_id),node=snapshot.nodes.find(item=>item.id===action.step_id);
      const selected=action.input_bindings.map(binding=>resolveEnterpriseGraphResultForHost(snapshot,binding.result_ref,limits));
      const ownResults=snapshot.results.filter(item=>item.producer.action_id===action.id);
      const ownProducts=products.filter(item=>item.action_id===action.id&&item.attempt_id===attemptId&&same(item.owner,owner));
      const ownReceipts=receipts.filter(item=>item.action_id===action.id&&item.attempt_id===attemptId&&same(item.owner,owner));
      const results=[...ownResults,...selected],allowed=new Set([...ownProducts.map(item=>item.ref),...ownReceipts.map(item=>item.ref),
        ...results.flatMap(item=>[item.result_ref,...item.artifact_refs,...item.observation_refs])]);
      const mode=payload.mode??'metadata';requireCycle(['metadata','text'].includes(mode),'Choose metadata or text inspection');
      if(payload.ref)requireCycle(allowed.has(payload.ref),'Reference was not admitted for this exact action or selected input');
      if(onBinding){
        const binding=executeCheckpoints.get(action.id);
        requireCycle(binding&&same(binding.action,action),'Inspection has no committed public execute checkpoint');
        onBinding(freeze(clone(binding)));
      }
      let value;
      const result=results.find(item=>item.result_ref===payload.ref),product=ownProducts.find(item=>item.ref===payload.ref);
      if(mode==='text'){
        requireCycle(opaque(payload.ref)&&!results.some(item=>item.result_ref===payload.ref)&&Number.isSafeInteger(payload.offset_bytes)&&payload.offset_bytes>=0&&
          Number.isSafeInteger(payload.length_bytes)&&payload.length_bytes>0,'Text inspection needs an exact content ref and explicit byte range');
        graphCapacity('graph_reference_read_bytes',payload.length_bytes,Math.min(capacities.product_excerpt_bytes??capacities.tool_observation_bytes,
          limits.resultBytes??limits.publicBytes,limits.publicBytes));
        requireCycle(typeof readReferenceContent==='function','The host reference reader is unavailable');
        value=await readReferenceContent({action:freeze(clone(action)),ref:payload.ref,offset_bytes:payload.offset_bytes,length_bytes:payload.length_bytes},{signal,requestKey:callId});
        signal.throwIfAborted();currentExecute(action.id);
        requireCycle(value?.ref===payload.ref&&!Object.hasOwn(value,'path')&&!Object.hasOwn(value,'handles'),'Host inspection returned an invalid reference projection');
      }else if(payload.ref&&!result){
        requireCycle(payload.offset_bytes===undefined&&payload.length_bytes===undefined,'Metadata inspection does not take a byte range');
        if(product)value=productView(product);
        else{
          requireCycle(typeof readReferenceContent==='function','The host reference reader is unavailable');
          value=await readReferenceContent({action:freeze(clone(action)),ref:payload.ref},{signal,requestKey:callId});
          signal.throwIfAborted();currentExecute(action.id);
          requireCycle(value?.ref===payload.ref&&value.text===undefined,'Metadata inspection must not read content');
        }
      }else{
        requireCycle(payload.offset_bytes===undefined&&payload.length_bytes===undefined,'Metadata inspection does not take a byte range');
        value={action_id:action.id,declared_outputs:clone(node.outputs),
          products:ownProducts.filter(item=>!payload.ref||item.ref===payload.ref).map(productView),
          observation_refs:ownReceipts.filter(item=>!payload.ref||item.ref===payload.ref).map(item=>item.ref),
          results:results.filter(item=>!payload.ref||item.result_ref===payload.ref).map(item=>
            reduceEnterpriseGraph(snapshot,'resolve',{result_ref:item.result_ref},host(),limits).result)};
      }
      if(payload.ref&&!result){
        requireCycle(value&&Object.keys(value).every(key=>['ref','kind','logical_path','roles','sha256','bytes','offset_bytes','read_bytes','next_offset_bytes','content_status','content_reason','utf8_boundary_trimmed','text'].includes(key))&&
          value.ref===payload.ref&&['product','observation'].includes(value.kind)&&/^[a-f0-9]{64}$/.test(value.sha256)&&Number.isSafeInteger(value.bytes)&&value.bytes>0,
          'Host inspection returned an invalid immutable descriptor');
        if(value.logical_path!==undefined)requireCycle(typeof value.logical_path==='string'&&!value.logical_path.startsWith('/')&&
          !value.logical_path.includes('\\')&&value.logical_path.split('/').every(part=>part&&part!=='.'&&part!=='..'),'Inspection cannot expose private paths');
        if(mode==='text'){
          const range=value.offset_bytes===payload.offset_bytes&&Number.isSafeInteger(value.read_bytes)&&value.read_bytes>=0&&value.read_bytes<=payload.length_bytes;
          requireCycle(value.content_status==='text'?range&&typeof value.text==='string'&&Buffer.byteLength(value.text)<=payload.length_bytes:
            value.content_status==='metadata_only'&&value.text===undefined&&(value.offset_bytes===undefined||range),
            'Host inspection returned an invalid bounded range');
        }
      }
      return resultReply({...value,action_id:action.id,step_id:action.step_id,inspection_only:true});
    }catch(error){signal?.throwIfAborted();interruptDebug(error);return errorReply(error);}
    finally{referenceReads.delete(abort);}
  }
  async function commitProposal(action,proposal,signal){
    requireCycle(proposal&&nativeStatuses.has(proposal.status)&&Array.isArray(proposal.receipts)&&Array.isArray(proposal.products)&&typeof proposal.output==='string',
      'Host dispatch returned an invalid native proposal');
    const admitted=proposal.receipts.map(item=>checkedAdmission(item,action));
    const inspected=await inspectVersions(action,proposal.products,signal);
    const dispatch=dispatches.find(item=>item.action_id===action.id),node=snapshot.nodes.find(item=>item.id===action.step_id);
    let association;
    if(proposal.handoff){
      try{association=validatedProposal(action,node,proposal.handoff,admitted,inspected);}
      catch(error){association={status:'rejected',code:error.code??'node_proposal_rejected',message:publicText(error.message),...(error.diagnostic?{diagnostic:clone(error.diagnostic)}:{})};}
    }else if(proposal.partial_handoff&&workEdition){
      // Revalidate the same sealed subset at final commit. It never acquires a
      // complete proposal ref and cannot be used by the shorthand route.
      try{association=validatedProposal(action,node,proposal.partial_handoff,admitted,inspected,{inspect_partial:true});}
      catch(error){association={status:'rejected',code:error.code??'node_proposal_rejected',message:publicText(error.message),...(error.diagnostic?{diagnostic:clone(error.diagnostic)}:{})};}
    }else if(proposal.handoff_error)association=clone(proposal.handoff_error);
    else if(dispatch?.contract_schema)association={status:'missing',code:'node_proposal_missing',message:'The native execution returned no structured slot/check proposal. Retained bytes and execution status are unchanged. Correct associations explicitly or record actual limitations.'};
    let capacityError;
    try{checkBytes('graph_child_proposal_bytes',proposal,limits.resultBytes??limits.publicBytes);}
    catch(error){if(!error.capacity)throw error;capacityError=clone(error.capacity);}
    const data=stateData();data.receipts=appendUnique(data.receipts,admitted);data.products=appendUnique(data.products,inspected);
    if(proposal.computation){requireCycle(!proposal.computation.action_id||proposal.computation.action_id===action.id,'Computation has another action');
      data.computations.push({action_id:action.id,...clone(proposal.computation)});}
    const result=reduceEnterpriseGraph(snapshot,'execution_settled',{action_id:action.id,status:proposal.status},
      host({receipts:data.receipts,products:data.products}),limits);
    data.snapshot=result.state;
    data.dispatches=data.dispatches.map(item=>item.action_id===action.id?{...item,status:proposal.status,
      receipt_refs:admitted.map(value=>value.ref),product_refs:inspected.map(value=>value.ref),
      ...(association?{proposal:association}:{}),
      ...(proposal.proposal_diagnostics?{proposal_diagnostics:clone(proposal.proposal_diagnostics)}:{}),
      ...(proposal.persistence?{persistence:clone(proposal.persistence)}:{}),
      ...(proposal.capacity?{capacity_recovery:clone(proposal.capacity)}:{}),
      ...(capacityError?{capacity_error:capacityError}:{output:proposal.output})}:item);
    await persist('settle-'+hash(action.id).slice(0,32),data,result.events,action.id,signal);
    proposals.delete(action.id);
    if(capacityError)lastError='research_capacity_exceeded';
  }
  function own(promise){background.add(promise);promise.finally(()=>background.delete(promise)).catch(()=>{});return promise;}
  function launch(action,node,at){
    if(jobs.has(action.id))return;
    const abort=new AbortController();
    const promise=(async()=>{
      let proposal,enteredNative=false;
      try{
        const inputs=await inputContext(action,abort.signal);abort.signal.throwIfAborted();
        requireCycle(!snapshot.work_envelope||Date.now()<snapshot.work_envelope.finish_by_ms,'The shared child work window has ended');
        enteredNative=true;
        proposal=await dispatchNode({action:freeze(clone(action)),node:freeze(clone(node)),inputs,checkpoint:freeze(clone(at)),
          ...(dispatches.find(item=>item.action_id===action.id)?.contract_schema?{contract_schema:'capstone-node-contract/1'}:{}),
          ...(snapshot.work_envelope?{work_envelope:freeze(clone(snapshot.work_envelope))}:{}),
          ...(turnGuidance()?{turn_guidance:turnGuidance()}:{})},{signal:abort.signal,
          validateProposal:candidate=>{
            abort.signal.throwIfAborted();
            try{
              const current=currentExecute(action.id);
              requireCycle(same(current,action)&&snapshot.node_states[action.step_id].phase==='executing',
                'Proposal feedback requires its exact active immutable execute action');
            }catch(error){error.correctable=false;error.diagnostic={code:'action_unavailable',field:'binding'};throw error;}
            return validatedProposal(action,node,candidate.handoff,candidate.receipts.map(item=>checkedAdmission(item,action)),
              candidate.products.map(item=>checkedAdmission(item,action,true)),{metadata:candidate.metadata,selected_paths:candidate.selected_paths,inspect_partial:candidate.inspect_partial});
          }});
      }catch(error){
        // A throw after native entry has no proven execution status. Cancellation
        // is known only when the executor confirms it in its proposal.
        proposal={status:enteredNative?'unknown':abort.signal.aborted?'cancelled':'failed',receipts:[],products:[],
          output:enteredNative?'Native execution did not return a confirmed host proposal.':'Native execution did not start because input admission failed or the job was cancelled.'};
      }
      proposals.set(action.id,{action:clone(action),proposal});
      try{await serial(async()=>{if(pending)return;await commitProposal(action,proposal);});}
      catch(error){
        lastError=error.code??'research_native_settlement_not_confirmed';
      }
    })().finally(()=>{jobs.delete(action.id);pulse();own(pump().catch(error=>{lastError=error.code??'research_schedule_failed';}));});
    jobs.set(action.id,{promise,abort,action:clone(action)});own(promise);
  }
  async function pump(){
    if(pumping)return pumping;
    pumping=(async()=>{
      await load();
      while(!closed&&!closing&&!delivery&&!pending&&!proposals.size&&jobs.size<concurrency){
        if(snapshot?.work_envelope&&Date.now()>=snapshot.work_envelope.finish_by_ms)break;
        const node=snapshot?.nodes.find(item=>item.execution==='delegated'&&snapshot.node_states[item.id].phase==='ready'&&
          snapshot.node_states[item.id].applicability==='current');
        if(!node)break;
        let issued;
        try{await serial(async()=>{
          if(pending||closed||closing||delivery)return;
          if(snapshot?.work_envelope&&Date.now()>=snapshot.work_envelope.finish_by_ms)return;
          const result=reduceEnterpriseGraph(snapshot,'start',{step_id:node.id},host(),limits);
          const action=graphAction(result.state,result.state.node_states[node.id].execute_action_id),data=stateData();
          data.snapshot=result.state;data.dispatches.push({action_id:action.id,step_id:node.id,status:'intent',contract_schema:'capstone-node-contract/1'});
          ownedIntents.add(action.id);
          await persist('auto-start-'+hash(action.id).slice(0,32),data,result.events,action.id);
          issued={action,node,checkpoint:clone(checkpoint)};
        });}catch(error){lastError=error.code??'research_start_not_confirmed';break;}
        if(!issued)break;launch(issued.action,issued.node,issued.checkpoint);
      }
    })();
    try{await pumping;}finally{pumping=undefined;}
  }
  async function recoverLocked(signal){
    signal?.throwIfAborted();if(!pending)return;
    // Request identity and bytes remain fixed. A new AbortSignal is a transport
    // concern only and cannot change the retained CAS body.
    pending.signal=signal;const recovered=await acknowledge();
    // A committed acknowledgement can arrive after the caller stopped waiting.
    // Adopt it, but do not start native work for an aborted admission.
    signal?.throwIfAborted();
    const intents=recovered.saved.dispatches.filter(item=>item.status==='intent'&&ownedIntents.has(item.action_id));
    for(const intent of intents){
      const action=graphAction(snapshot,intent.action_id),node=snapshot.nodes.find(item=>item.id===action.step_id);
      if(node.execution==='delegated'&&snapshot.node_states[node.id].phase==='executing'&&!jobs.has(action.id)&&!proposals.has(action.id)&&!closed&&!closing&&!delivery)
        launch(action,node,checkpoint);
    }
  }
  async function reconcileLocked(signal){
    await recoverLocked(signal);
    for(const item of [...proposals.values()]){if(pending)break;await commitProposal(item.action,item.proposal,signal);}
  }
  async function recoverPending({signal}={}){
    signal=admissionSignal(signal);
    try{await waitFor(load(),signal);}
    catch(error){signal.throwIfAborted();if(!loaded||!pending)throw error;}
    await serial(()=>reconcileLocked(signal),signal);
    await waitFor(pump(),signal);return controller.readState({signal});
  }
  function parentSettlement(action,context){
    const node=snapshot.nodes.find(item=>item.id===action.step_id);
    const actionReceipts=context.receipts.filter(item=>item.action_id===action.id);
    const status=actionReceipts.some(item=>item.status==='unknown')?'unknown':actionReceipts.some(item=>item.status==='cancelled')?'cancelled':
      actionReceipts.some(item=>item.status==='completed')?'completed':actionReceipts.some(item=>item.status==='failed')?'failed':
      node.mode==='synthesis'&&action.input_bindings.length?'completed':'unknown';
    return freeze({action_id:action.id,status});
  }
  async function settleParent(action,settlement,context,signal,origin){
    requireCycle(![...tokens].some(token=>token.action.id===action.id),'This parent action still has active native tools');
    const transition=reduceEnterpriseGraph(snapshot,'execution_settled',settlement,context,limits);
    const data=stateData();data.snapshot=transition.state;
    await persist('parent-settle-'+hash(action.id).slice(0,32),data,transition.events,action.id,signal,origin);
  }
  async function execute(operation,callId,payload,options={}){
    if(advisoryReviews&&operation==='assess'&&payload?.action_id&&!Object.hasOwn(payload,'goal_review'))
      return noteNodeReview(callId,payload,options);
    if(!lightweightTasks||operation!=='record'||!advisoryReviews&&!Object.hasOwn(payload??{},'assessment'))
      return executeSingle(operation,callId,payload,options);
    try{
      const {assessment:requestedAssessment,...record}=payload;
      const assessment=advisoryReviews?{outcome:record.outcome==='completed'?'success':'limited',
        summary:'Returned work registered. Analytical review is diagnostic; user acceptance remains open.'}:requestedAssessment;
      requireCycle(assessment&&typeof assessment==='object'&&!Array.isArray(assessment)&&
        Object.keys(assessment).every(key=>['outcome','summary','checks'].includes(key))&&
        ['success','limited','failure'].includes(assessment.outcome)&&typeof assessment.summary==='string'&&assessment.summary.trim(),
        'A combined return needs an explicit outcome and assessment summary');
      const selected={...assessment,...(record.proposal_ref&&!Object.hasOwn(assessment,'checks')
        ?{proposal_ref:record.proposal_ref}:{checks:assessment.checks??[]})};
      validateGraphOperation('assess',{action_id:'combined-assessment',...selected},limits,workEdition);
      const recorded=await executeSingle(operation,callId,record,options);
      if(recorded.details?.ok!==true)return recorded;
      const recordedResult=recorded.details.result;
      const actionId=recordedResult.graph.nodes.find(node=>node.id===recordedResult.step_id)?.assess_action_id;
      const assessed=await executeSingle('assess','record-assessment:'+hash(callId).slice(0,40),
        {action_id:actionId,...selected},options);
      const note=advisoryReviews&&requestedAssessment?await noteNodeReview('record-note:'+hash(callId).slice(0,40),
        {...requestedAssessment,action_id:actionId},options):undefined;
      return {...assessed,details:{...assessed.details,recorded:{action_id:recordedResult.action_id,step_id:recordedResult.step_id},
        ...(note?{review_note:note.details}:{} )}};
    }catch(error){options.signal?.throwIfAborted();interruptDebug(error);return errorReply(goalError(error),undefined,operation);}
  }
  async function noteNodeReview(callId,payload,{signal}={}){
    try{
      signal=admissionSignal(signal);await waitFor(load(),signal);
      return await serial(async()=>{
        await reconcileLocked(signal);
        const replay=commandReceipt(callId,'assess',payload);if(replay)return clone(replay.reply);
        requireCycle(!pending&&!closed&&!closing&&!delivery,'The graph is closed or unconfirmed');
        const action=graphAction(snapshot,payload.action_id);
        const output={graph:publicState(),action_id:action.id,step_id:action.step_id,diagnostic_only:true,
          review_note:clone(payload),scope:'Model review note only. No source admission, verification pass, rejection or rerun.'};
        const current=await view(),at={ref:prefix+hash('call:'+callId).slice(0,24),revision:current.research_revision+1};
        const data=stateData(),reply=resultReply(output,at);
        data.commands.push({id:callId,operation:'assess',payload_hash:hash(payload),reply});
        graphCapacity('graph_command_receipts',data.commands.length,limits.maxExecutions*8);
        await persist(callId,data,[],action.id,signal,callId);return reply;
      },signal);
    }catch(error){signal?.throwIfAborted();interruptDebug(error);return errorReply(goalError(error),undefined,'assess');}
  }
  async function executeSingle(operation,callId,payload,{signal}={}){
    try{
      signal=admissionSignal(signal);await waitFor(load(),signal);requireCycle(operations.includes(operation),'Only bound model graph operations are allowed');
      if(config.researchRuntime?.adaptiveAgentLoop===true&&['plan','revise'].includes(operation)){
        const refs=[...new Set((payload?.nodes??[]).flatMap(node=>node.source_refs??[]))];
        const admitted=await prepareSources?.(refs,{signal});
        for(const source of admitted??[]){
          const previous=sources.find(item=>item.ref===source.ref);
          requireCycle(!previous||hash(previous)===hash(source),'Source version changed');
          if(!previous)sources.push(clone(source));
        }
      }
      if(goalDriven&&operation==='assess'&&Object.hasOwn(payload??{},'goal_review'))return await assessGoal(callId,payload,signal);
      const submitted=clone(payload);
      let proposedOrganization;
      if(goalDriven&&operation==='plan'){
        proposedOrganization=createTaskGoal(payload?.requirements,limits);
        payload={...payload};delete payload.requirements;
      }
      if(lightweightTasks&&['plan','revise'].includes(operation)&&Array.isArray(payload?.nodes)){
        payload={...payload,nodes:payload.nodes.map(node=>node&&typeof node==='object'&&!Array.isArray(node)
          ? {depends_on:[],inputs:[],checks:[],...node,
            questions:node.questions===undefined||node.questions?.length===0?[node.purpose]:node.questions,
            expected_outputs:node.expected_outputs===undefined||node.expected_outputs?.length===0
              ?(Array.isArray(node.outputs)?node.outputs.map(output=>output?.description):[]):node.expected_outputs}:node)};
        for(const node of payload.nodes)requireCycle(Array.isArray(node?.source_refs),
          'Task source_refs is required. Select exact refs from the granted source catalog for each task; top-level sources do not grant child access. Use [] only for a task needing no original source.');
        if(operation==='plan')payload.source_refs=[...new Set(payload.nodes.flatMap(node=>node.source_refs))];
      }
      requireCycle(opaque(callId),'Tool command ID must be an opaque reference');payload=validateGraphOperation(operation,payload,limits,workEdition);
      const identityPayload=goalDriven&&operation==='plan'?submitted:payload;
      if(isolatedTasks&&payload.nodes)requireCycle(payload.nodes.every(node=>node.execution==='delegated'),
        'Every executable node requires an independent task executor');
      if(isolatedTasks&&operation==='start')requireCycle(payload.kind==='assess','Task execution starts through the orchestrator');
      const replay=commandReceipt(callId,operation,identityPayload);if(replay)return clone(replay.reply);
      const reply=await serial(async()=>{
        await reconcileLocked(signal);
        const old=commandReceipt(callId,operation,identityPayload);if(old)return clone(old.reply);
        requireCycle(!pending&&!closed&&!closing&&!delivery,'The graph is closing, closed, or unconfirmed');
        if(goalDriven&&!lightweightTasks&&operation==='revise')requireCycle(organization?.review?.decision==='continue'&&
          organization.review.basis===goalContext().basis,'Assess the current whole goal as continue before changing the next task batch');
        if(operation==='start'&&payload.kind!=='assess'){
          const node=snapshot?.nodes.find(item=>item.id===payload.step_id);
          requireCycle(node?.execution==='parent','Delegated nodes are started only by the committed scheduler');
          requireCycle(!snapshot.nodes.some(item=>item.execution==='parent'&&snapshot.node_states[item.id].phase==='executing'&&item.id!==node.id),
            'Only one parent execute action can own native tools');
        }
        let expanded=proposalPayload(operation,payload),assessmentNotes=[];
        if(lightweightTasks&&operation==='assess'){
          const action=graphAction(snapshot,expanded.action_id),node=snapshot.nodes.find(item=>item.id===action.step_id);
          const execution=snapshot.executions.find(item=>item.step_id===action.step_id&&item.execution_revision===action.execution_revision);
          for(const item of expanded.checks)requireCycle(item.refs.every(ref=>execution?.admitted_observations.includes(ref)),
            'Assessment reference was not admitted');
          assessmentNotes=expanded.checks.filter(item=>!node.checks.includes(item.description));
          expanded={...expanded,checks:expanded.checks.filter(item=>node.checks.includes(item.description))};
        }
        if(lightweightTasks&&operation==='assess'&&expanded.outcome==='success'){
          const action=graphAction(snapshot,expanded.action_id),node=snapshot.nodes.find(item=>item.id===action.step_id);
          const execution=snapshot.executions.find(item=>item.step_id===action.step_id&&item.execution_revision===action.execution_revision);
          const current=snapshot.node_states[action.step_id];
          // Research findings remain usable without turning unperformed checks
          // into passes. The reducer still validates action and source identity.
          if(execution?.record?.outcome==='completed'&&(
            node.checks.some(description=>!expanded.checks.some(check=>check.description===description&&check.status==='passed'))||
            node.outputs.some(slot=>!current.output_bindings.some(binding=>binding.slot===slot.slot)))){
            expanded={...expanded,outcome:'limited'};
          }
        }
        if(isolatedTasks&&operation==='revise'){
          requireCycle(new Set(payload.nodes.map(node=>node.id)).size===payload.nodes.length,'Duplicate task IDs in incremental revision');
          const replacements=new Map(payload.nodes.map(node=>[node.id,node])),existing=snapshot?.nodes??[];
          expanded={...expanded,nodes:[...existing.map(node=>replacements.get(node.id)??clone(node)),
            ...payload.nodes.filter(node=>!existing.some(prior=>prior.id===node.id))]};
        }
        const command=freeze(expanded);
        const computation=payload.action_id?computations.find(item=>item.action_id===payload.action_id):undefined;
        const context=freeze(clone(host({computation})));
        if(operation==='record'){
          const action=graphAction(snapshot,payload.action_id),node=snapshot.nodes.find(item=>item.id===action.step_id);
          requireCycle(![...tokens].some(token=>token.action.id===action.id),'This action still has active native tools');
          const settlement=node.execution==='parent'&&snapshot.node_states[node.id].phase==='executing'?parentSettlement(action,context):null;
          // Discard both pure projections: no lease, result or event is
          // published until the entire record passes the real reducer.
          const preview=settlement?reduceEnterpriseGraph(snapshot,'execution_settled',settlement,context,limits).state:snapshot;
          reduceEnterpriseGraph(preview,'record',command,context,limits);
          if(settlement)await settleParent(action,settlement,context,signal,callId);
        }
        const transition=reduceEnterpriseGraph(snapshot,operation,command,context,limits),data=stateData();data.snapshot=transition.state;
        if(proposedOrganization)data.organization=proposedOrganization;
        if(goalDriven&&lightweightTasks&&operation==='revise')
          data.organization=reviewTaskGoal(organization,{decision:'continue',requirements:[],summary:payload.reason},
            {...goalContext(transition.graph),review_ref:'goal-review:'+hash({taskId,callId,operation}).slice(0,48)});
        const actionId=payload.action_id??(operation==='start'?transition.state.node_states[payload.step_id][payload.kind==='assess'?'assess_action_id':'execute_action_id']:undefined);
        const boundAction=actionId?graphAction(transition.state,actionId):undefined;
        const output={graph:transition.graph,...(goalDriven?{organization:data.organization}:{}),...(boundAction?{action_id:boundAction.id,step_id:boundAction.step_id}:{}),
          ...(assessmentNotes.length?{assessment_notes:assessmentNotes}:{}),
          ...(payload.proposal_ref?{proposal_ref:payload.proposal_ref}:{}),...(transition.result?{result:transition.result}:{})};
        const current=await view(),at={ref:prefix+hash('call:'+callId).slice(0,24),revision:current.research_revision+1};
        const frozenReply=resultReply(output,at);
        data.commands.push({id:callId,operation,payload_hash:hash(identityPayload),reply:frozenReply});
        graphCapacity('graph_command_receipts',data.commands.length,limits.maxExecutions*8);
        await persist(callId,data,transition.events,actionId,signal,callId);return frozenReply;
      },signal);
      await waitFor(pump(),signal);return reply;
    }catch(error){signal?.throwIfAborted();interruptDebug(error);error=goalError(error);return errorReply(error,assessmentFeedback(operation,payload,error),operation);}
  }
  async function assessGoal(callId,payload,signal){
    const ignored=advisoryReviews?['action_id','outcome','checks','proposal_ref','summary']:[];
    requireCycle(opaque(callId)&&payload&&Object.hasOwn(payload,'goal_review')&&
      Object.keys(payload).every(key=>key==='goal_review'||ignored.includes(key)),
      'Choose exactly goal_review or the existing node assessment fields');
    return serial(async()=>{
      await reconcileLocked(signal);
      const replay=commandReceipt(callId,'assess',payload);if(replay)return clone(replay.reply);
      requireCycle(snapshot&&!pending&&!closed&&!closing&&!delivery,'A current open graph is required for whole-goal review');
      checkBytes('graph_goal_review_bytes',payload,limits.publicBytes);
      const context={...goalContext(),review_ref:'goal-review:'+hash({taskId,callId,payload}).slice(0,48)};
      const data=stateData();data.organization=reviewTaskGoal(organization,payload.goal_review,context);
      const current=await view(),at={ref:prefix+hash('call:'+callId).slice(0,24),revision:current.research_revision+1};
      const ignoredFields=Object.keys(payload).filter(key=>key!=='goal_review');
      const reply=resultReply({graph:publicState(),organization:data.organization,
        ...(ignoredFields.length?{diagnostics:{ignored_node_review_fields:ignoredFields}}:{})},at);
      data.commands.push({id:callId,operation:'assess',payload_hash:hash(payload),reply});
      graphCapacity('graph_command_receipts',data.commands.length,limits.maxExecutions*8);
      await persist(callId,data,[],undefined,signal,callId);return reply;
    },signal);
  }
  function finishPayload(payload){
    requireCycle(payload&&Object.keys(payload).sort().join(',')==='delivery_product_refs,delivery_result_refs,limitations,outcome,summary'&&
      ['success','limited','failure'].includes(payload.outcome)&&typeof payload.summary==='string'&&payload.summary.trim(), 'Invalid explicit graph delivery');
    for(const key of ['delivery_result_refs','delivery_product_refs','limitations']){
      requireCycle(Array.isArray(payload[key])&&new Set(payload[key]).size===payload[key].length,'Delivery lists must be explicit and unique');
      graphCapacity('graph_delivery_items',payload[key].length,limits.maxItems);
      for(const item of payload[key])requireCycle(typeof item==='string'&&item.trim()&&item.length<=limits.maxText&&
        (key==='limitations'||opaque(item)),'Invalid bounded delivery reference or limitation');
    }
    graphCapacity('graph_delivery_summary',payload.summary.length,limits.maxText);
    requireCycle(payload.outcome==='success'||payload.limitations.length>0,'Limited or failed delivery needs explicit limitations');
  }
  function validateDelivery(payload){
    requireCycle(snapshot,'A committed graph is required');
    if(goalDriven)validateTaskGoalFinish(organization,payload,goalContext());
    const current=snapshot.nodes.map(node=>snapshot.node_states[node.id]);
    if(payload.outcome==='success')requireCycle(current.every(item=>item.phase==='success'&&item.applicability==='current')&&
      snapshot.executions.every(item=>item.settled_status!=='unknown')&&!jobs.size&&!tokens.size,'Successful delivery requires accepted successful current nodes and known native outcomes');
    const selected=payload.delivery_result_refs.map(ref=>{
      const result=snapshot.results.find(item=>item.result_ref===ref),state=result&&snapshot.node_states[result.producer.step_id];
      requireCycle(result&&state.applicability==='current'&&settledPhases.has(state.phase)&&state.output_bindings.some(item=>item.result_ref===ref),
        'Delivery must select exact current model-assessed result versions');return result;
    });
    requireCycle(payload.outcome!=='success'||selected.every(result=>!result.input_limitations?.length),
      'Selected results inherit explicitly accepted limited inputs; choose limited delivery and retain their limitations');
    requireCycle(payload.outcome!=='success'||selected.length>0,'Successful delivery needs explicit current result references');
    requireCycle(payload.delivery_product_refs.every(ref=>selected.some(result=>result.artifact_refs.includes(ref))&&products.some(item=>item.ref===ref&&item.status==='ready')),
      'Delivery products must be inspected artifacts of selected current results');
    const selectedProducts=deliveryGrants(payload);
    for(const ref of payload.delivery_product_refs){
      const failed=selected.some(result=>result.artifact_refs.includes(ref)&&snapshot.node_states[result.producer.step_id].phase==='failure');
      if(failed){const matches=selectedProducts.filter(item=>item.ref===ref);
        requireCycle(payload.outcome!=='success'&&matches.length>0&&matches.every(product=>Array.isArray(product.roles)&&product.roles.length>0&&
          product.roles.every(role=>['support','reproduction'].includes(role))),
          'A failed assessment may supply only explicitly marked diagnostic support or reproduction products');}
    }
    const limitedTurn=lightweightTasks&&goalDriven&&organization.review?.decision==='limited'&&payload.outcome==='limited';
    const actualArtifact=lightweightTasks&&selected.some(result=>result.kind==='artifact'&&result.artifact_refs.some(ref=>payload.delivery_product_refs.includes(ref))&&
      ['success','limited'].includes(snapshot.node_states[result.producer.step_id].phase));
    requireCycle(snapshot.output_mode!=='files'||payload.outcome==='failure'||limitedTurn||actualArtifact||selectedProducts.some(product=>product.roles?.includes('primary')),
      'Successful or limited file delivery requires an actual inspected primary product; diagnostics alone are not the requested report');
  }
  function deliveryGrants(payload){
    const selected=snapshot.results.filter(result=>payload.delivery_result_refs.includes(result.result_ref));
    const result=[];
    for(const ref of payload.delivery_product_refs){
      const matching=products.filter(item=>item.ref===ref&&item.status==='ready'&&same(item.owner,owner)&&item.attempt_id===attemptId);
      // Resolve each selected result separately, then combine its grants. A
      // sibling's direct grant cannot hide another selected result's lineage.
      const visit=(manifest,visited=new Set())=>{
        if(!manifest||!manifest.artifact_refs.includes(ref)||visited.has(manifest.result_ref))return [];
        visited.add(manifest.result_ref);
        const direct=matching.filter(item=>item.action_id===manifest.producer.action_id);
        if(direct.length)return direct;
        return manifest.consumed_results.flatMap(consumed=>visit([...snapshot.results,...snapshot.external_results].find(item=>item.result_ref===consumed),visited));
      };
      for(const manifest of selected.filter(item=>item.artifact_refs.includes(ref))){
        const grants=visit(manifest);
        requireCycle(grants.length>0,'Each selected result needs its own direct or explicit lineage artifact grant');
        for(const product of grants)
          if(!result.some(item=>item.ref===product.ref&&item.action_id===product.action_id&&item.attempt_id===product.attempt_id))result.push(product);
      }
      requireCycle(result.some(item=>item.ref===ref),'A selected artifact has no matching result grant');
    }
    return result;
  }
  async function finish(callId,payload,{signal}={}){
    try{
      signal=admissionSignal(signal);await waitFor(load(),signal);requireCycle(opaque(callId),'Finish command ID must be opaque');
      const {goal_review_ref,...core}=payload??{};
      finishPayload(goalDriven?core:payload);
      if(goalDriven)requireCycle(opaque(goal_review_ref),'Finish requires an exact whole-goal review reference');
      let replay;
      await serial(async()=>{
        await reconcileLocked(signal);
        replay=commandReceipt(callId,'finish',payload);if(replay)return;
        requireCycle(!closed&&!delivery&&!pending,'The graph is closed or unconfirmed');
        requireCycle(!tokens.size,'Finish requires all parent native tools to return before closure');
        requireCycle(!closing||closing.command_id===callId&&same(closing.payload,payload),'Recover the already selected graph closure command');
        validateDelivery(payload);
        if(payload.outcome!=='success'&&!closing){
          const data=stateData();data.closing={command_id:callId,payload:clone(payload)};
          await persist('closing-'+hash(callId).slice(0,32),data,[],undefined,signal,callId);
        }
      },signal);
      if(replay)return clone(replay.reply);
      if(payload.outcome!=='success')await waitFor(drain('Model explicitly closed the graph'),signal);
      return await serial(async()=>{
        await reconcileLocked(signal);
        requireCycle(!pending&&!closed&&!delivery,'Native settlement requires exact checkpoint recovery and one closure');validateDelivery(payload);
        // Recheck current physical product versions immediately before delivery.
        const selectedProducts=deliveryGrants(payload);
        for(const actionId of new Set(selectedProducts.map(item=>item.action_id)))
          await inspectVersions(graphAction(snapshot,actionId),selectedProducts.filter(item=>item.action_id===actionId),signal);
        const inherited=snapshot.results.filter(result=>payload.delivery_result_refs.includes(result.result_ref)).flatMap(result=>result.input_limitations??[]);
        const delivered={...clone(goalDriven?core:payload),limitations:[...new Set([...payload.limitations,...inherited.flatMap(item=>[
          item.assessment_summary,...item.record_limitations,...item.unmet_checks.map(check=>check.description+': '+check.status+' — '+check.explanation)])])]};
        graphCapacity('graph_delivery_items',delivered.limitations.length,limits.maxItems);
        checkBytes('graph_delivery_bytes',delivered,limits.publicBytes);
        const data=stateData();data.delivery=delivered;data.closing=null;
        const output={graph:publicState(),delivery:publicText(clone(delivered))};
        // Public text uses the reducer's filter through a bounded result-free
        // graph field. Delivery metadata contains only admitted refs and text.
        const current=await view(),at={ref:prefix+hash('call:'+callId).slice(0,24),revision:current.research_revision+1};
        const reply=resultReply(output,at);data.commands.push({id:callId,operation:'finish',payload_hash:hash(payload),reply});
        await persist(callId,data,[{kind:'graph_delivery_committed',...publicText(clone(delivered))}],undefined,signal,callId);closed=true;return reply;
      },signal);
    }catch(error){signal?.throwIfAborted();interruptDebug(error);return errorReply(goalError(error));}
  }
  async function drain(reason){
    for(const job of jobs.values())job.abort.abort(new DOMException(reason,'AbortError'));
    await Promise.allSettled([...jobs.values()].map(item=>item.promise));
    await Promise.allSettled([...background]);await writer;
  }
  async function inspectParent(callId,payload,{signal}={}){
    try{
      signal=admissionSignal(signal);await waitFor(load(),signal);requireCycle(opaque(callId),'Inspection command ID must be opaque');
      requireCycle(payload&&Object.keys(payload).sort().join(',')==='action_id,products'&&opaque(payload.action_id)&&Array.isArray(payload.products)&&payload.products.length>0,
        'Inspection requires an exact parent action and product selections');
      graphCapacity('graph_inspection_products',payload.products.length,limits.maxItems);
      requireCycle(new Set(payload.products.map(item=>item.path)).size===payload.products.length,'Inspection paths must be unique');
      for(const item of payload.products)requireCycle(item&&Object.keys(item).sort().join(',')==='path,role'&&
        typeof item.path==='string'&&item.path.length>0&&item.path.length<=Math.min(limits.maxText,1024)&&!item.path.startsWith('/')&&!item.path.includes('\\')&&
        item.path.split('/').every(part=>part&&part!=='.'&&part!=='..')&&!/[\x00-\x1f]/.test(item.path)&&
        ['primary','support','reproduction'].includes(item.role),'Inspection needs safe relative paths and published presentation roles');
      const replay=commandReceipt(callId,'inspect',payload);if(replay)return clone(replay.reply);
      return await serial(async()=>{
        await reconcileLocked(signal);
        const old=commandReceipt(callId,'inspect',payload);if(old)return clone(old.reply);
        requireCycle(!pending&&!proposals.size&&!closed&&!closing&&!delivery,'Inspection is blocked by closing or unconfirmed state');
        const action=graphAction(snapshot,payload.action_id),node=snapshot.nodes.find(item=>item.id===action.step_id),current=snapshot.node_states[node.id];
        requireCycle(action.kind==='execute'&&node.execution==='parent'&&current.execute_action_id===action.id&&current.phase==='executing',
          'Inspection requires the current explicitly started parent execute action');
        requireCycle(![...tokens].some(token=>token.action.id===action.id),'Wait for this parent action native tools before product inspection');
        const inspected=await inspectProducts({snapshot:clone(snapshot),action:clone(action),products:clone(payload.products)},{signal,requestKey:callId});
        requireCycle(inspected?.ready===true&&Array.isArray(inspected.products)&&inspected.products.length===payload.products.length,
          'Host inspection did not confirm every requested product');
        const admitted=inspected.products.map(item=>checkedAdmission(item,action,true));
        const selections=inspected.selections??admitted.map(item=>({path:item.path,ref:item.ref}));
        requireCycle(Array.isArray(selections)&&selections.length===payload.products.length&&
          selections.every(item=>item&&Object.keys(item).sort().join(',')==='path,ref'&&typeof item.path==='string'&&opaque(item.ref))&&
          new Set(selections.map(item=>item.path)).size===selections.length&&new Set(selections.map(item=>item.ref)).size===selections.length&&
          payload.products.every(selection=>{
            const bound=selections.find(item=>item.path===selection.path),product=bound&&admitted.find(item=>item.ref===bound.ref);
            return product&&same(product.roles,[selection.role]);
          })&&new Set(admitted.map(item=>item.ref)).size===admitted.length,
          'Host inspection must bind every selected source path to its exact sealed product and role');
        const data=stateData();data.products=appendUnique(data.products,admitted);
        const currentView=await view(),at={ref:prefix+hash('call:'+callId).slice(0,24),revision:currentView.research_revision+1};
        const output={products:admitted.map(({ref,path,sha256,bytes,roles})=>({ref,path,sha256,bytes,roles:clone(roles)})),graph:publicState()};
        const reply=resultReply(output,at);data.commands.push({id:callId,operation:'inspect',payload_hash:hash(payload),reply});
        await persist(callId,data,[],action.id,signal,callId);return reply;
      },signal);
    }catch(error){signal?.throwIfAborted();interruptDebug(error);return errorReply(error);}
  }
  const controller={execute,finish,inspect:inspectParent,recoverPending,readReference,
    // Private model context only. Never place these handles in durable state or tool replies.
    async readParentInputs({signal}={}){
      signal=admissionSignal(signal);await recoverPending({signal});await waitFor(writer,signal);
      requireCycle(!pending,'Parent inputs require a confirmed checkpoint');
      const action=activeParent();if(!action)return null;
      const key=hash(action);
      if(!parentInputs.has(key)){
        let job=parentResolutions.get(key);
        if(!job){
          const abort=new AbortController(),control=AbortSignal.any([signal,abort.signal]);
          const promise=inputContext(action,control).then(inputs=>{control.throwIfAborted();
            requireCycle(same(activeParent(),action),'Parent input action changed during resolution');
            parentInputs.set(key,inputs);return inputs;}).finally(()=>parentResolutions.delete(key));
          job={abort,promise};
          parentResolutions.set(key,job);
        }
        await waitFor(job.promise,signal);
      }
      signal.throwIfAborted();requireCycle(same(activeParent(),action),'Parent input action is no longer active');
      return clone({action,inputs:parentInputs.get(key)});
    },
    async readState({compact=false,signal}={}){await waitFor(load(),signal);await waitFor(writer,signal);const value={phase:delivery?(delivery.outcome==='success'?'done':delivery.outcome):closing?'closing':snapshot?'active':'idle',
      graph:publicState(),checkpoint:clone(checkpoint),...(goalDriven?{organization:organizationView()}:{}),...(workStatus()?{work_budget:workStatus()}:{}),
      ...(turnGuidance()?{turn_guidance:turnGuidance()}:{}),update_pending:Boolean(pending),settlement_pending:[...proposals.keys()],
      pending_proposals:dispatches.filter(item=>nativeStatuses.has(item.status)&&!settledPhases.has(snapshot.node_states[item.step_id].phase)).map(item=>({action_id:item.action_id,step_id:item.step_id,status:item.status,
        ...(item.proposal?{proposal:publicText(clone(item.proposal))}:{}),
        ...(item.persistence?{persistence:publicText(clone(item.persistence))}:{}),
        receipt_refs:clone(item.receipt_refs??[]),product_refs:clone(item.product_refs??[]),
        declared_outputs:clone(snapshot.nodes.find(node=>node.id===item.step_id).outputs),
        products:products.filter(product=>product.action_id===item.action_id&&item.product_refs?.includes(product.ref)).map(productView),
        ...(item.output!==undefined?{output:publicText(item.output)}:{}),...(item.capacity_error?{capacity_error:clone(item.capacity_error)}:{})})),delivery:publicText(clone(delivery))};
      if(compact){
        value.graph=graphReferences(value.graph);
        value.pending_proposals=value.pending_proposals.map(({output,...reference})=>reference);
      }
      checkBytes('graph_read_state_bytes',value,limits.publicBytes);return value;},
    async progressKey({signal}={}){await waitFor(load(),signal);await waitFor(writer,signal);return semanticProgress();},
    /** PRIVATE HOST ONLY. Never register this exact proposal as a public tool.
     * The SDK must create an authorized bounded model projection/handle. */
    async readProposal(actionId){
      await load();await writer;graphAction(snapshot,actionId);
      const proposal=dispatches.find(item=>item.action_id===actionId&&nativeStatuses.has(item.status));
      requireCycle(proposal,'No committed native result proposal exists for this action');
      if(proposal.capacity_error){const error=new EnterpriseCycleError('research_capacity_exceeded','Native proposal exceeded its explicit result budget. Actual settlement and admitted receipts remain saved.');
        error.capacity=clone(proposal.capacity_error);interruptDebug(error);throw error;}
      const value={action:graphAction(snapshot,actionId),status:proposal.status,output:proposal.output??'',
        receipts:receipts.filter(item=>item.action_id===actionId&&proposal.receipt_refs?.includes(item.ref)),
        products:products.filter(item=>item.action_id===actionId&&proposal.product_refs?.includes(item.ref)),
        ...(computations.find(item=>item.action_id===actionId)?{computation:computations.find(item=>item.action_id===actionId)}:{})};
      checkBytes('graph_private_proposal_bytes',value,limits.resultBytes??limits.publicBytes);return clone(value);
    },
    register(pi){
      for(const operation of operations)pi.registerTool({name:names[operation],label:'Research '+operation,
        parameters:clone(parameters[operation]),description:(advisoryReviews?{
          plan:'Declare immutable whole-goal requirements as {id,description,kind:finding|artifact} and submit only the next justified task or batch. Tasks have independent contexts. Use record for returned findings; the host automatically settles nodes. Append justified tasks with revise, without a separate node review or continue review call. Review the whole goal when deciding actual delivery.',
          revise:'Submit the next justified independent tasks with reason and rerun:[] for new work. This operation itself records the decision to continue; a separate whole-goal continue review is not required. Existing unresolved requirements remain open. Do not retransmit existing tasks just to append new ones.',
          record:'Register a validated return as {action_id:EXACT_EXECUTE_ACTION_ID,outcome:completed|limited|failed,proposal_ref:EXACT_RETURNED_PROPOSAL_REF,limitations:[]}. Choose exactly one proposal_ref or explicit outputs; omit outputs when using proposal_ref. If no validated proposal exists, supply actual outputs and omit proposal_ref. The host automatically settles the node and continues ready work. No separate node assessment or verification pass is required. Missing checks and partial results remain limitations, without a rejection or rerun gate.',
          assess:'Review the whole goal when deciding delivery using only {goal_review:{decision:continue|complete|limited|blocked,requirements:[{id,status:satisfied|open|blocked,result_refs:[],explanation}],summary}}. Omit all node-assessment fields from this form. Cite exact current result refs for satisfied coverage; artifact coverage needs an actual saved artifact. Send changed coverage; the host retains prior current support and leaves other requirements open. Use limited for useful delivery with unmet requirements disclosed. Copy the returned organization.review.review_ref into finish.goal_review_ref. Node-level review, if supplied separately, is only a diagnostic note: it cannot reject a node, undo its return or demand rework. Use record to register actual findings; the host handles node settlement.'
        }[operation]:undefined)??(goalDriven?{
          plan:'Declare immutable overall requirements as {id,description,kind:finding|artifact}. Preserve distinct substantive questions and requested deliverables as outcomes, separate from executable tasks. Submit only the next justified independent task or batch; do not merge unrelated investigations to reduce task count. After returns, record/assess node results and assess the whole goal.',
          assess:'Choose exactly one of three forms. (1) Adopt a validated producer proposal: {action_id,proposal_ref,outcome,summary}. Omit checks entirely. (2) Assess explicit checks: {action_id,outcome,checks:[{description,status,refs,explanation}],summary}. Omit proposal_ref entirely; use description, never label. '+operationDescriptions.assess+' (3) Review the whole goal: {goal_review:{decision:continue|complete|limited|blocked,requirements:[{id,status:satisfied|open|blocked,result_refs:[],explanation,blocker?:{kind,explanation}}],summary}}. Omit all node-assessment fields in form 3. Review all requirements incrementally: send changed coverage, and the host retains current prior support or leaves omitted requirements open. Satisfied coverage cites exact current accepted result refs; artifact coverage needs an actual saved artifact. Continue with open requirements when more work is needed now; use limited for an explicit useful research-turn delivery with unmet requirements disclosed. Hard-limit blockers require an actually reached native deadline. After complete or limited review, copy organization.review.review_ref into finish.goal_review_ref.'
        }[operation]:undefined)??(isolatedTasks&&['plan','revise','start'].includes(operation)?{
          plan:'Commit only the next evidence-supported task or batch, never a speculative complete workflow. All executable nodes use delegated execution, including discovery and synthesis. Preserve the overall goal. The host schedules ready tasks; accept their returned results before deciding the next tasks.',
          revise:'Submit only new tasks or changed unstarted tasks. The host retains every omitted existing definition exactly; do not retransmit or reconstruct started tasks. Append the next evidence-supported tasks after accepted results reveal remaining requirements. Do not predeclare unknown downstream work. All executable nodes use delegated execution.',
          start:'Start assessment of recorded work with kind assess. All execution is scheduled by the orchestrator in independent task contexts; the planner cannot execute a node.'
        }[operation]:operationDescriptions[operation]),
        execute:(callId,payload,signal)=>execute(operation,callId,payload,{signal})});
      if(!isolatedTasks)pi.registerTool({name:'agent_research_inspect',label:'Inspect research products',parameters:clone(graphInspectToolParameters),
        description:'Ask the host to freeze and inspect selected parent output files. Supply safe relative paths and presentation roles. Only a committed host grant supplies artifact refs for record; inspection is not execution or quality evidence.',
        execute:(callId,payload,signal)=>inspectParent(callId,payload,{signal})});
      const finishParameters=clone(graphFinishToolParameters);
      if(goalDriven){finishParameters.properties.goal_review_ref=clone(ref);finishParameters.required.push('goal_review_ref');}
      pi.registerTool({name:'agent_research_finish',label:'Finish research',parameters:finishParameters,
        description:(goalDriven?'Requires exact goal_review_ref from a current complete or limited whole-goal assessment. A continue decision forbids finish: append the next justified tasks. A limited decision preserves unmet requirements and needs explicit limitations and an actual retained result. A blocked goal may close only as failure. A performance estimate is not a hard deadline. ':'')+'Explicitly close delivery. Before closing, '+(advisoryReviews?'record every contributing node; the host settles it automatically, with no separate node assessment. ':'record and assess every node whose output should contribute, including settled children. ')+'Host drain/cancellation settles jobs but does not record their outputs. Select exact current assessed result refs and their inspected artifact refs. Use success only when all current nodes succeeded with known native outcomes; limited or failure remains valid with explicit limitations. Once finish commits, later record/assess calls are rejected. Node success alone is not task delivery.',
        execute:(callId,payload,signal)=>finish(callId,payload,{signal})});
    },
    async beginTool({toolCallId,toolName,signal}){
      signal=admissionSignal(signal);await waitFor(load(),signal);
      if(config.researchRuntime?.adaptiveAgentLoop===true&&!snapshot&&!pending&&!closed&&!closing&&!delivery)return null;
      requireCycle(!isolatedTasks,'Native work requires an independent task executor');
      requireCycle(toolName!=='agent_delegate','Manual delegation is not permitted on the graph route');
      requireCycle(!toolName.startsWith('agent_research_'),'Graph control tools are not native execution');
      return serial(async()=>{
        await reconcileLocked(signal);
        requireCycle(!pending&&!proposals.size&&!closed&&!closing&&!delivery,'Native work is blocked by closing or unconfirmed state');
        const parent=snapshot?.nodes.filter(node=>node.execution==='parent'&&snapshot.node_states[node.id].phase==='executing');
        requireCycle(parent?.length===1,'Native tools require one explicitly started parent action');
        requireCycle(![...tokens].some(item=>item.toolCallId===toolCallId),'Native tool call is already active');
        requireCycle(!receipts.some(item=>item.tool_call_id===toolCallId)&&!toolReceipts.has('tool-'+hash(toolCallId).slice(0,32)),
          'This native tool call already has a retained receipt; do not execute it again');
        const action=graphAction(snapshot,snapshot.node_states[parent[0].id].execute_action_id);
        const token=freeze({toolCallId,toolName,action,checkpoint:clone(checkpoint)});tokens.add(token);return token;
      },signal);
    },
    endTool(token,result,error,{signal}={}){
      if(!tokens.has(token))return;tokens.delete(token);
      const status=signal?.aborted||error?.name==='AbortError'?'cancelled':error||result?.isError===true?'failed':'completed';
      const source=result?.details?.native_research_source?.source_ref;
      // An unwrapped tool can record a failure/unknown settlement, but cannot
      // manufacture a successful observation handle from its model text.
      const receipt={ref:opaque(source)?source:'execution-receipt:'+hash(taskId+'\0'+token.toolCallId),owner:clone(owner),
        action_id:token.action.id,attempt_id:attemptId,status:status==='completed'&&!opaque(source)?'unknown':status,tool_name:token.toolName,tool_call_id:token.toolCallId};
      const id='tool-'+hash(token.toolCallId).slice(0,32);toolReceipts.set(id,{receipt,action_id:token.action.id});
      if(receipt.status==='completed')nativeProgress.add(hash({action_id:token.action.id,tool_name:token.toolName,
        content:(result.content??[]).filter(item=>item.type!=='text'||!item.text.startsWith('Host observation reference: '))}));
      // Keep native tools outside the CAS control lane. The next graph or
      // sibling settlement checkpoint includes these exact action-keyed receipts.
      pulse();
    },
    async completeTool(token,result,{signal}={}){this.endTool(token,result,undefined,{signal});await writer;signal?.throwIfAborted();return result;},
    async continuationState({signal}={}){
      signal=admissionSignal(signal);await recoverPending({signal});
      if(delivery){if(goalDriven&&delivery.outcome==='failure')fail('task_goal_blocked','The whole goal is blocked; partial results are retained, not completed delivery.');return null;}
      // No accepted work exists to continue. Let the same first model turn answer
      // a simple request directly; do not manufacture a planning turn after it.
      if(!snapshot&&!pending&&!closing&&!jobs.size)return null;
      const control=()=>snapshot?.nodes.some(node=>{const current=snapshot.node_states[node.id];return ['executed','recorded','assessing'].includes(current.phase)||
        node.execution==='parent'&&current.phase==='ready';});
      // Checkpoint and scheduling pulses do not necessarily deliver a result.
      // Re-check the predicate before spending another planner model turn.
      while(!delivery&&!pending&&!closing&&!control()&&jobs.size){
        await new Promise((resolve,reject)=>{
          const done=()=>{signal?.removeEventListener('abort',abort);waiters.delete(done);resolve();};
          const abort=()=>{waiters.delete(done);reject(signal.reason??new DOMException('Aborted','AbortError'));};
          signal?.throwIfAborted();waiters.add(done);signal?.addEventListener('abort',abort,{once:true});
        });await recoverPending({signal});
      }
      if(delivery){if(goalDriven&&delivery.outcome==='failure')fail('task_goal_blocked','The whole goal is blocked; partial results are retained, not completed delivery.');return null;}
      const state=await this.readState({compact:true,signal});
      if(state.update_pending)fail('research_update_not_confirmed','A scheduled checkpoint is still unconfirmed after host recovery. Retain its exact request; native work was not repeated.');
      if(config.runtimeLimitMode==='debug'&&config.researchRuntime?.lightweightTaskNodes!==true){
        const exceeded=state.pending_proposals.find(item=>item.capacity_error);
        if(exceeded){const error=new EnterpriseCycleError('research_capacity_exceeded','Native output exceeded its explicit result budget.');
          error.capacity=exceeded.capacity_error;interruptDebug(error);}
      }
      const newlyDelivered=[];
      state.pending_proposals=state.pending_proposals.map(reference=>{
        const proposal=dispatches.find(item=>item.action_id===reference.action_id);
        if(deliveredProposalOutputs.has(reference.action_id)||proposal.output===undefined)return reference;
        newlyDelivered.push(reference.action_id);
        return {...reference,output:publicText(proposal.output)};
      });
      const packet={instruction:(goalDriven?(advisoryReviews?
        'Keep whole-goal requirements visible. Record returned findings; the host settles nodes automatically, with checks diagnostic only. Append the next justified tasks with revise, which records continue without a separate review call. Use whole-goal review when choosing complete or limited delivery; retain remaining gaps and do not claim user acceptance. ':
        'Keep organization.requirements alive independently of the submitted tasks. After each accepted result/batch use assess with goal_review to review all requirements, then revise when decision is continue. A complete review permits successful/limited finish. An explicit limited review permits useful turn delivery with unmet requirements disclosed; this is not user acceptance. Blocked permits failure only. Do not use estimated performance targets as hard deadlines. '):'')+(isolatedTasks?'Plan only the next evidence-supported task or batch. Every executable task, including synthesis, uses an independent context. After accepting results, compare remaining requirements with the user goal and append justified tasks using revise with only the new node definitions; the host retains existing tasks unchanged. An empty task pool is not goal completion. Do not execute native analysis in the planner. ':'')+
        'Use exact graph/action/proposal refs. Newly available native proposal text is supplied once. '+(advisoryReviews?'Record actual proposal_ref associations; the host settles nodes with no separate node assessment. ':'Record validated proposal_ref associations and explicitly assess their quality; parent outcome/summary are your judgment. ')+'Read agent_research_read section="overview" only to recover missing declarations or retained proposal text after compaction. '+(isolatedTasks?'':'Start ready parent work explicitly. ')+
        'When only children are running and no parent decision is actionable, end this response and yield; the host waits and wakes you on settlement. Do not poll overview. Finish with exact selected delivery or explicit limitations.',
        ...state};checkBytes('graph_continuation_bytes',packet,limits.publicBytes);
      for(const actionId of newlyDelivered)deliveredProposalOutputs.add(actionId);
      return {prompt:JSON.stringify(packet),actionId:pending?.saved.command_id??state.graph?.actions[0]?.id??state.graph?.graph_ref??'initialization',
        checkpoint:checkpoint?.revision??0,progress_key:semanticProgress()};
    },
    async close({signal,reason='Session closed'}={}){
      await load();closed=true;
      for(const job of parentResolutions.values())job.abort.abort(new DOMException('Parent input resolution cancelled','AbortError'));
      for(const abort of referenceReads)abort.abort(new DOMException('Reference inspection cancelled','AbortError'));
      parentInputs.clear();await drain(reason);signal?.throwIfAborted();pulse();
      if(pending)fail('research_update_not_confirmed','Session jobs were drained, but a checkpoint still requires exact receipt recovery');
      if(proposals.size)fail('research_native_settlement_not_confirmed','Native jobs returned but result persistence is not confirmed; retain and reconcile their exact proposals');
      if(tokens.size)fail('research_native_tools_not_drained','Parent native tools must settle before session disposal');
      if(snapshot&&toolReceipts.size)await serial(()=>persist('close-receipts-'+hash([...toolReceipts.keys()]).slice(0,32),stateData(),[]));
    },
    get status(){return freeze({status:lastError??(delivery?'settled':'active'),phase:delivery?(delivery.outcome==='success'?'done':delivery.outcome):closing?'closing':snapshot?'active':'idle',
      graph_schema:'capstone-enterprise-graph/2',update_pending:Boolean(pending),running:jobs.size});},
  };
  return controller;
}
