/** Application-owned same-session research adapter. The existing channel owns CAS and replay. */
import {createHash} from 'node:crypto';
import {runtimeLimits as resolveLimits,runtimeLimitMode,checkCapacity,CapacityExceeded} from './runtime-limits.mjs';
import {assertDeliveryReview,deliveryReviewStatus,isTrustedDeliveryReview} from './delivery-review.mjs';
import {readFileSync} from 'node:fs';
import {reduceEnterpriseCycle,readyObjectivesAfterAssessment} from './enterprise-cycle-state.mjs';
import {cycleToolParameters,cycleOperationToolParameters,validateBoundCycleOperation,EnterpriseCycleError} from './enterprise-cycle-contract.mjs';
const splitTools={plan:'agent_research_plan',record:'agent_research_record',assess:'agent_research_assess'};
const controlTools=new Set(['agent_research_cycle',...Object.values(splitTools)]);
const hash=value=>createHash('sha256').update(value).digest('hex');
function canonical(value){return Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?
  Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;}
function viewJson(value){return Array.isArray(value)?'['+value.map(viewJson).join(', ')+']':value&&typeof value==='object'?
  '{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+': '+viewJson(value[key])).join(', ')+'}':JSON.stringify(value);}
const CHECKPOINT='capstone-enterprise-cycle-checkpoint/1',DISPATCH_CHECKPOINT='capstone-enterprise-cycle-checkpoint/2';
const checkpointSchemas=new Set([CHECKPOINT,DISPATCH_CHECKPOINT]),terminal=new Set(['done','blocked','limited']);
const cycleGuidance=`Enterprise research protocol:
Before substantive tools, commit a plan with purpose, questions, expected_outputs and checks. Follow the Domain Pack's research method to choose and revise objectives.
For independent child investigations, declare objective.subtasks in the plan or assessment follow_ups. Each subtask has id, title, instruction, questions, expected_outputs and depends_on. The host dispatches this accepted graph automatically and returns delegation results with the control response; do not issue another agent_delegate call for the same work. Use [] for independent subtask dependencies and exact subtask IDs for real prerequisites. Keep the related child questions in one investigation objective instead of serial objective steps when they can run independently. The host runs ready children concurrently and queues excess work. Interpret actual returned statuses; do not claim overlap merely because delegation was requested. After results, record and assess the accepted objective, then revise future work from observed gaps. Parent integration is not a compulsory repeat of each child check.
For an accepted execute action without subtasks, an agent_delegate batch is bound to that action. Each task needs questions copied from pending_action.questions, expected_outputs and a self-contained instruction. Its returned result is an observation for parent integration and assessment, not automatic acceptance. For an action with subtasks, only the host dispatches children. If its checkpoint is unconfirmed, repeat the same research control request to recover the retained result; never replace it with a manual batch.
Children do not inherit the parent conversation or source-discovery findings. In each instruction, include the relevant observed field names, units, grain, join keys, source paths and known limitations from completed discovery, with their source references. Label these as prior observations to check where consequential, not independent verification. Do not ask a child to guess whether a field exists after discovery has answered it. Do not request unavailable dimensions or substitute speculative proxy analyses for measures already present in the supplied sources.
Give each shared intermediate calculation one owner. If another child needs its saved result, declare that dependency and consume the returned path and definition; do not independently rebuild the same aligned data. Assign charts to their producing analysis or to final integration, not both. Cross-topic analysis should resolve a concrete user question or an observed gap; do not add broad correlation matrices, alternative aggregation panels or exhaustive subgroup studies merely because several datasets are available. A first draft can report a scoped unresolved relationship without expanding every branch.
Delegate a question, relevant input references, expected evidence and a clear completion condition. Let the child choose its method; do not turn a small question into a long procedural checklist, an exhaustive audit or an extra report. Request saved files only when needed for the user's deliverable or later dependent work. Match checking depth to the requested decision and material uncertainty. Further checks need a concrete discrepancy, missing evidence or explicit user requirement; hypothetical alternatives alone do not require another investigation. Integrate the returned evidence and limitations rather than repeating a child's checks by default. Conflicting or insufficient evidence requires a focused follow-up, not automatic acceptance.
Record actual results and inspected files, then assess in a separate call. Reflection and derived_from reference retained finding IDs; supersedes references obsolete pending objectives and newly proposed replacements. Follow-ups become pending work and preserve the previous plan history.
First delivery is a usable draft for continuing human review, not a clean audit verdict. A local check or attempted repair that remains unsuccessful must be recorded as a limitation; continue integrating the usable report instead of repeatedly repairing it. Preserve available child results when another branch is incomplete. Missing optional analysis or failed advisory review does not prevent producing the requested readable report with clearly marked gaps. Finish with limited status and truthful failed/not_run checks where needed; do not claim a missing or unreadable report was delivered. Access control, source integrity and persistence failures still require explicit handling.
Use exact action IDs, source refs and check labels returned by the host. Initial plan objectives use resolves: []; resolves means IDs of assessed incomplete objectives, not problems or output names. Finding IDs are immutable; use a new ID when revising a finding. Each cycle transition must be alone in its tool batch; wait for its result before work tools. Independent work tools may run together.
To recover an action ID or accepted delegation questions, use agent_research_read with section="overview" and read cycle.pending_action. Ledger open_questions are not the current action's questions. Record returns a new assess action ID; never reuse its preceding execute ID for assessment.
Report concise public findings and decisions, not private reasoning. A step spans the work needed to answer its question; do not record/assess after every tool. Deliver when the requested questions have sufficient supported answers and actual usable outputs. Preserve valid work and state material limitations. Repeated unchanged rejected operations are not progress.`;
const safeCodes={research_reference_not_admitted:'A source was not admitted. Use host-issued successful observations or frozen sources; unsupported findings remain hypotheses.',
  research_revision_conflict:'The committed research revision changed. Recover the protected view before correcting the call.',
  research_update_not_confirmed:'Recover the same unconfirmed checkpoint before new work; do not repeat source execution.'};

export function createEnterpriseResearchController({config,commitResearch,readResearch,inspectProducts,onProgress=()=>{},dispatchSubtasks}){
  if(typeof config?.researchTaskId!=='string'||!config.researchAttemptId||!config.researchOwner||
      ![commitResearch,readResearch,inspectProducts,onProgress].every(fn=>typeof fn==='function'))
    throw new TypeError('Enterprise research requires frozen owner, Attempt and protected ports');
  const runId=config.researchTaskId,owner=hash(runId).slice(0,20);
  const allowed=config.applicationPolicy?.allowed_tools;
  const split=Array.isArray(allowed)&&Object.values(splitTools).some(name=>allowed.includes(name));
  const entrances=split?Object.values(splitTools).filter(name=>allowed.includes(name)):
    (!Array.isArray(allowed)||allowed.includes('agent_research_cycle')?['agent_research_cycle']:[]);
  const entrance=operation=>split?splitTools[operation]:`agent_research_cycle with operation="${operation}"`;
  const defaults=JSON.parse(readFileSync(new URL('./application-capacity.json',import.meta.url),'utf8')).limits;
  const capacities=resolveLimits({...defaults,...config.runtimeLimits},{mode:config.runtimeLimitMode});
  const options={maxRounds:capacities.research_question_count,maxFindings:capacities.research_claim_count,
    maxQuestions:capacities.research_question_count,snapshotBytes:capacities.control_document_bytes,...config.researchRuntime?.limits,
    mode:runtimeLimitMode(capacities),batchReadyInvestigations:config.researchRuntime?.batchReadyInvestigations===true};
  const sources=new Set(config.researchSources??[]),tokens=new Set(),pendingWrites=new Map(),projected=new Set();
  let snapshot,receipts=[],products=[],loaded=false,busy=false,attemptedCycle=false,lastRepair,progressRevision=0;
  let pending,activeCall,committed,activeSignal,currentCheckpoint,lastStatus='idle';
  let requestedDelivery;
  const dispatches=new Map();
  async function view(){const result=await readResearch();if(!result||!Number.isSafeInteger(result.research_revision)||result.research_revision<0)
    throw new Error('Protected research view is invalid');return result;}
  function checkpointNote(key){return `runtime.${key.startsWith('dispatch:')?'dispatch':'checkpoint'}.${owner}.${hash(key).slice(0,24)}`;}
  function claimsFor(state){return state.findings.map(item=>({claim_id:'runtime.'+hash(runId+'\0'+item.id).slice(0,40),
    statement:item.text,status:item.status==='hypothesis'?'pending':item.status,refs:item.refs}));}
  function capacity(dimension,actual,unit) {
    const limit=capacities[dimension];
    if(limit!==undefined&&actual>limit) {
      if(runtimeLimitMode(capacities)==='debug')checkCapacity(capacities,dimension,actual,unit,'research_runtime');
      const error=new Error('Configured research capacity was exceeded');error.code='research_capacity_exceeded';
      error.capacity={dimension,actual,limit,unit};throw error;
    }
  }
  async function persist(key,state,status,claims=[],refs=[],signal=activeSignal) {
    signal?.throwIfAborted();
    const noteId=checkpointNote(key), requestId='runtime-'+hash(runId+'\0'+key);
    let request=pendingWrites.get(requestId);
    if(!request) {
      const current=await view();
      const notes=current.state?.notes??[], previous=notes.find(note=>note.note_id===noteId);
      // Already committed in this channel: restore/read the immutable note,
      // rather than generating a changed request at a newer revision.
      if(previous) {
        const saved=JSON.parse(previous.text);
        if(!checkpointSchemas.has(saved.schema)||saved.runId!==runId)throw new Error('Research checkpoint identity changed');
        committed=structuredClone(saved);
        progressRevision=current.research_revision;
        return {checkpointRef:noteId,revision:current.research_revision};
      }
      const note={note_id:noteId,text:JSON.stringify({schema:state.objectives.some(item=>item.subtasks)?DISPATCH_CHECKPOINT:CHECKPOINT,runId,status,snapshot:state,receipts,products,cycleCall:activeCall,
        dispatches:[...dispatches],...(key.startsWith('dispatch:')?{action_checkpoint:currentCheckpoint}:{})}),refs};
      capacity('research_text_chars',Array.from(note.text).length,'codepoints');
      const merged=new Map((current.state?.claims??[]).map(item=>[item.claim_id,item]));
      for(const claim of claims)merged.set(claim.claim_id,claim);
      // The owning reducer merges notes and claims by ID. Submit only this
      // delta; old immutable checkpoints remain in the existing ledger/view.
      const changes={notes:[note],claims};
      if(!current.state)changes.goal=state.goal;
      request={expected_revision:current.research_revision,changes};
      capacity('research_request_bytes',Buffer.byteLength(JSON.stringify({request_id:'request-'+hash(requestId),...request})+'\n'),'bytes');
      const nextRevision=current.research_revision+1;
      const candidate={...current,research_revision:nextRevision,state:{...(current.state??{}),
        ...(!current.state?{goal:state.goal,...(current.research_id?{research_id:current.research_id}:{})}:{}),
        claims:[...merged.values()],notes:[...notes,note],revision:nextRevision}};
      capacity('research_response_bytes',Buffer.byteLength(viewJson(candidate)+'\n'),'bytes');
      pendingWrites.set(requestId,request);
    }
    signal?.throwIfAborted();
    const response=await commitResearch(requestId,structuredClone(request),signal);
    const ack=response?.details?.result;
    if(response?.details?.ok!==true||ack?.status!=='committed') {
      const error=new Error(ack?.status==='rejected'?'Research checkpoint was rejected: '+(ack.code??'research_update_rejected')+'. No update was committed.':'Research checkpoint is not confirmed');
      error.code=ack?.code??response?.details?.error?.code??'research_update_not_confirmed';
      error.status=ack?.status??'not_confirmed';
      if(error.status==='rejected') {pendingWrites.delete(requestId);error.definiteRejected=true;}
      throw error;
    }
    if(!Number.isSafeInteger(ack.receipt?.research_revision)||ack.receipt.research_revision<1)
      throw new Error('Research checkpoint receipt is invalid');
    pendingWrites.delete(requestId);
    committed={snapshot:structuredClone(state),status,receipts:structuredClone(receipts),products:structuredClone(products)};
    progressRevision=ack.receipt.research_revision;
    return {checkpointRef:noteId,revision:ack.receipt.research_revision};
  }
  async function load(){
    if(loaded)return;const current=await view();
    for(const item of [...(current.state?.claims??[]),...(current.state?.notes??[])])for(const ref of item.refs??[])sources.add(ref);
    const note=[...(current.state?.notes??[])].reverse().find(item=>
      item.note_id.startsWith(`runtime.checkpoint.${owner}.`)||item.note_id.startsWith(`runtime.dispatch.${owner}.`));
    if(note){const saved=JSON.parse(note.text);
      if(!checkpointSchemas.has(saved.schema)||saved.runId!==runId||JSON.stringify(canonical(saved.snapshot.owner))!==JSON.stringify(canonical(config.researchOwner))||saved.snapshot.attempt_id!==config.researchAttemptId)
        throw new Error('Research checkpoint owner is invalid');
      snapshot=structuredClone(saved.snapshot);receipts=structuredClone(saved.receipts??[]);products=structuredClone(saved.products??[]);
      for(const [id,dispatch] of saved.dispatches??[])dispatches.set(id,dispatch);
      lastStatus=snapshot.phase;committed=structuredClone(saved);progressRevision=current.research_revision;attemptedCycle=true;
      currentCheckpoint=saved.action_checkpoint??{ref:note.note_id,revision:current.research_revision};
      for(const receipt of receipts)if(receipt.status==='completed')sources.add(receipt.ref);
    }loaded=true;
  }
  const host=()=>({owner:config.researchOwner,attempt_id:config.researchAttemptId,sources:[...sources],receipts,products});
  const rebuttalRefs=()=>new Set([...sources].filter(ref=>ref.startsWith('material:')||ref.startsWith('resource:'))
    .concat(receipts.filter(item=>item.status==='completed'&&item.tool_name==='read').map(item=>item.ref)));
  const scopeProducts=scope=>(scope??snapshot?.delivery_products??snapshot?.active_products??[]).map(item=>{
    const inspected=products.find(product=>product.path===item.path);
    return inspected??{...item};
  });
  function reviewStatus(scope=requestedDelivery){
    return {...deliveryReviewStatus(scopeProducts(scope),receipts,snapshot?.findings??[],rebuttalRefs(),products),
      selection_status:scope?'requested_not_committed':snapshot?.delivery_products?'committed':'legacy_all_recorded',
      inspection:'last_inspected; all selected products and review dependencies are revalidated at delivery'};
  }
  function action(state=snapshot){if(!state)return `Submit a corrected plan using ${entrance('plan')} with admitted source_refs and concrete objectives; the attempted cycle is not complete.`;
    const next=state.pending_action;
    if(!next)return `Report the actual ${state.phase} outcome and retained products and limitations.`;
    return next.kind==='execute'?`Execute action ${next.id}: ${next.purpose}. Expected outputs: ${next.expected_outputs.join('; ')}. `+
      (next.subtasks?.length?'The host owns this action’s subtask batch. Use its returned child results; do not call agent_delegate for this action. If the control checkpoint is unconfirmed, repeat the same control request to recover it without restarting children. ':
      config.researchRuntime?.explicitSubtaskPlanning===true?'This action declares parent-owned sequential work. Execute its accepted scope. New independent child work requires an accepted follow-up objective with subtasks; do not start an undeclared manual batch. ':
      'For independent questions in pending_action.questions, consider one agent_delegate batch with exact accepted questions, expected outputs and authorized source paths; the parent owns shared outputs and integration. Keep dependent work sequential and avoid delegation when it adds no useful independent work. ')+
      `Use real tools, then submit ${entrance('record')}; do not combine record and assessment.`:
      `Independently assess action ${next.id}: ${next.purpose}. Check recorded observations against completion conditions, then submit ${entrance('assess')}. `+
      (config.researchRuntime?.gracefulExecutionClosure===true&&state.objectives.find(item=>item.id===next.objective_id)?.product_paths?.length?
        'Producer files are already recorded: commit this assessment before more native work. If a new check is needed, record it as a follow-up objective; do not execute it under this assess ID. Unperformed advisory checks remain not_run and can lead to limited delivery. ':'')+
      'Connect consequential new questions to pending objectives with question_adoptions, or create sourced follow_ups. Review ready_if_current_met for independent work under the Domain Pack method; the list is conditional, not permission to start before this assessment commits. State limits for questions the admitted sources cannot answer. Keep adequate existing work.';}
  async function producerOutputMessage(action,objective,signal){
    const observed=await inspectProducts({snapshot,productRefs:[...objective.product_paths]},{signal});
    signal?.throwIfAborted();
    if(busy||pending||snapshot.pending_action?.id!==action.id)return null;
    const candidates=observed.products??[];
    const complete=observed.ready&&objective.product_paths.every(path=>candidates.some(item=>item.path===path&&
      /^[a-f0-9]{64}$/.test(item.sha256)&&Number.isSafeInteger(item.bytes)&&item.bytes>0));
    const changed=complete&&candidates.some(item=>!snapshot.active_products.some(registered=>registered.path===item.path&&
      registered.ref==='workspace-product:'+hash(JSON.stringify([item.path,item.sha256,item.bytes]))));
    return changed?`Observed producer output checkpoint for execute action ${action.id}: `+
      JSON.stringify(candidates.map(({path,sha256,bytes})=>({path,sha256,bytes})))+'. '+
      `File presence and version are not a quality verdict. Submit ${entrance('record')} with this execute ID, actual product_refs, truthful outcome completed/limited and limitations before further native checks or rewrites. `+
      'Then assess the returned new action ID. Advisory check or repair failures can remain recorded while an independent handoff proceeds; do not keep a producer in a checker loop.':null;
  }
  function success(state=snapshot,acceptedReceipts=receipts,findingIds=activeCall?.finding_ids??[]){const result={status:state.phase,phase:state.phase,round:state.round,pending_action:state.pending_action,next_action:action(state),
    product_refs:state.product_refs,...(state.delivery_products?{delivery_products:state.delivery_products}:{}),execution_receipts:acceptedReceipts.map(item=>({...item}))};
    if(state.phase==='assessing')result.planning_context=structuredClone({
      findings:state.findings.filter(item=>findingIds.includes(item.id)||state.pending_action.derived_from.includes(item.id)),
      retained_finding_ids:state.findings.map(item=>item.id),
      pending_objectives:state.objectives.filter(item=>item.status==='pending').map(({id,purpose,questions,depends_on,derived_from})=>
        ({id,purpose,questions,depends_on,derived_from:derived_from??[]})),
      ready_if_current_met:readyObjectivesAfterAssessment(state).map(({id,purpose,questions,expected_outputs,checks,depends_on,derived_from})=>
        ({id,purpose,questions,expected_outputs,checks,depends_on,derived_from:derived_from??[]})),
      previous_reflection:state.last_assessment?.reflection??null,
      limitations:state.limitations,
    });
    if(terminal.has(state.phase))result.limitations=[...state.limitations];
    if(state.phase==='limited'&&config.researchRuntime?.deliveryReview?.enabled===true&&state.output_mode==='files')
      result.delivery_review=deliveryReviewStatus(scopeProducts(state.delivery_products??state.active_products),acceptedReceipts,state.findings,rebuttalRefs(),products);
    return {content:[{type:'text',text:JSON.stringify(result)}],details:{capability:'agent_research_cycle',ok:true,result}};}
  async function inspect(params,signal){
    // Each research objective can produce different files. Reinspect the whole
    // active set; the latest record is not a replacement for earlier products.
    const declared=[...(snapshot?.active_products??[]).map(item=>item.path),
      ...(params.operation==='record'?params.product_refs:[]),
      ...(config.researchRuntime?.deliveryReview?.enabled===true&&params.operation==='assess'&&params.decision==='deliver'?
        receipts.flatMap(item=>item.review?.products?.map(product=>product.path)??[]):[])];
    if(!declared.length)return;
    const input=await inspectProducts({snapshot,productRefs:[...new Set(declared)]},{signal});
    if(params.operation==='record'&&!input.ready)throw new EnterpriseCycleError('research_products_unavailable',input.limitations?.join('; ')||'Declared saved products are unavailable');
    const checked=[];
    for(const item of input.products??[]){
      if(typeof item.path!=='string'||!/^[a-f0-9]{64}$/.test(item.sha256)||!Number.isSafeInteger(item.bytes)||item.bytes<1)
        throw new Error('Product inspector returned invalid identity');
      const ref='workspace-product:'+hash(JSON.stringify([item.path,item.sha256,item.bytes]));
      checked.push({...item,ref,status:'ready',attempt_id:config.researchAttemptId,action_id:snapshot.pending_action.id});
    }
    const registeredProducts=[...(committed?.products??[]),...products];
    products=checked;
    if(params.operation==='record')params.product_refs=params.product_refs.map(path=>{
      const item=checked.find(item=>item.path===path);if(!item)throw new EnterpriseCycleError('research_products_unavailable','Declared product was not inspected');return item.ref;});
    if(params.operation==='assess'&&params.delivery_product_refs!==undefined){
      const mismatches=params.delivery_product_refs.flatMap(path=>{
        const item=checked.find(product=>product.path===path),active=snapshot.active_products.find(product=>product.path===path);
        if(item&&active?.ref===item.ref)return [];
        const registered=registeredProducts.find(product=>product.path===path&&product.ref===active?.ref);
        return [{path,registered_ref:active?.ref??null,current_ref:item?.ref??null,
          registered_sha256:registered?.sha256??null,current_sha256:item?.sha256??null,
          status:!active?'unrecorded':item?'changed':'unavailable',reason:!active?'unrecorded':item?'changed_version':'unavailable'}];
      });
      if(mismatches.length){
        const changed=mismatches.some(item=>item.reason==='changed_version');
        const error=new EnterpriseCycleError(changed?'research_product_version_mismatch':'research_delivery_selection_invalid',
          'Final delivery selection contains '+(changed?'bytes changed since their registered versions':'unrecorded or unavailable products')+'. No version was rebound. '+
          'While still assessing, submit partial or unmet coverage with decision revise, omit delivery_product_refs, and add a repair follow-up with resolves: '+JSON.stringify([snapshot.pending_action.objective_id])+'. '+
          'Use its returned execute action to read and verify the retained current files, then record the affected paths to bind their actual new SHA. Obtain a review of those current bytes, then assess the returned new assess action separately. Do not rewrite correct files merely to register them; do not submit record with an assess action ID. Unrecorded files need real execution and recording first; unavailable files need restoration or an honest limited outcome.');
        const diagnostic={total:mismatches.length,truncated:false,products:[]};
        for(const item of mismatches){diagnostic.products.push(item);
          if(Buffer.byteLength(JSON.stringify({...diagnostic,truncated:true}))>options.snapshotBytes){diagnostic.products.pop();diagnostic.truncated=true;break;}}
        error.product_mismatches=diagnostic;throw error;
      }
      params.delivery_product_refs=params.delivery_product_refs.map(path=>{
        const item=checked.find(item=>item.path===path);
        return item.ref;
      });
      requestedDelivery=params.delivery_product_refs.map(ref=>{const item=checked.find(product=>product.ref===ref);return {path:item.path,ref};});
    }
  }
  async function publish(call,checkpoint){
    if(projected.has(checkpoint.ref))return;
    for(const {action_id:actionId,progress} of call.progress??[]){
      if(actionId)await onProgress({type:'enterprise_cycle_progress',owner:config.researchOwner,attempt_id:config.researchAttemptId,
        action_id:actionId,checkpoint,progress});
    }
    projected.add(checkpoint.ref);
  }
  async function settle(target){
    activeCall=target.call;
    activeCall.progress??=target.result.progress_events.map(progress=>({action_id:progress.phase==='settled'?
      snapshot?.pending_action?.id:target.result.state.pending_action?.id,progress}));
    const receipt=await persist(target.key,target.result.state,target.result.state.phase,claimsFor(target.result.state),
      [...new Set(target.result.state.findings.flatMap(item=>item.refs))]);
    snapshot=target.result.state;lastStatus=snapshot.phase;pending=undefined;lastRepair=undefined;
    requestedDelivery=undefined;
    currentCheckpoint={ref:receipt.checkpointRef,revision:receipt.revision};
    await publish(activeCall,{ref:receipt.checkpointRef,revision:receipt.revision});
    return success();
  }
  async function execute(callId,params,signal){
    if(busy)return {content:[{type:'text',text:'Research cycle is already advancing.'}],details:{ok:false,error:{code:'research_cycle_busy'}}};
    busy=true;activeSignal=signal;attemptedCycle=true;
    try{signal?.throwIfAborted();await load();
      if(pending)return await settle(pending);
      const payloadHash=hash(JSON.stringify(canonical(params))),key='call:'+callId;
      const current=await view(),old=current.state?.notes?.find(item=>item.note_id===checkpointNote(key));
      if(old){const saved=JSON.parse(old.text);if(saved.cycleCall?.hash!==payloadHash)throw new EnterpriseCycleError('research_call_identity_changed','Research tool call identity changed input');
        await publish(saved.cycleCall,{ref:old.note_id,revision:current.research_revision});return success(saved.snapshot,saved.receipts,saved.cycleCall?.finding_ids??[]);}
      if(tokens.size)throw new EnterpriseCycleError('research_execution_pending','Actual tool execution is still in progress. Wait for its result, then record or assess the settled action.');
      const operation=structuredClone(params);
      if(config.researchRuntime?.explicitSubtaskPlanning===true)
        for(const objective of operation.objectives??operation.follow_ups??[])
          if(!Object.hasOwn(objective,'subtasks'))
            throw new EnterpriseCycleError('research_subtask_plan_required','Each objective must declare subtasks: list substantial independent investigations for automatic host execution, or [] for parent-owned sequential work. Multiple questions alone do not create children.');
      for(const objective of operation.objectives??operation.follow_ups??[])if(objective.subtasks?.length){
        if(typeof dispatchSubtasks!=='function'||!allowed?.includes('agent_delegate'))
          throw new EnterpriseCycleError('research_delegation_unavailable','Automatic subtasks require the application-granted delegation executor.');
        checkCapacity(resolveLimits({research_delegation_tasks:config.researchRuntime?.delegation?.maxTasks??capacities.research_question_count},
          {mode:runtimeLimitMode(capacities)}),'research_delegation_tasks',objective.subtasks.length,'items','research_plan');
      }
      if(snapshot&&operation.operation!=='plan'&&operation.action_id!==snapshot.pending_action?.id){
        const safeId=value=>typeof value==='string'&&/^cycle-[a-f0-9]{64}$/.test(value)?value:null;
        const error=new EnterpriseCycleError('research_action_mismatch','Action does not match current pending action. Read agent_research_read section="overview" and copy cycle.pending_action.id; do not infer or reuse the preceding execute ID.');
        error.action_mismatch={expected_action_id:safeId(snapshot.pending_action?.id),submitted_action_id:safeId(operation.action_id),phase:snapshot.phase,objective_id:snapshot.pending_action?.objective_id??null};
        throw error;
      }
      await inspect(operation,signal);
      if(config.researchRuntime?.deliveryReview?.enabled===true&&operation.operation==='assess'&&operation.decision==='deliver'&&snapshot?.output_mode==='files'&&
        snapshot.phase==='assessing'&&operation.action_id===snapshot.pending_action?.id){
        const selected=operation.delivery_product_refs!==undefined?requestedDelivery:undefined;
        try{assertDeliveryReview(scopeProducts(selected),receipts,snapshot.findings,rebuttalRefs(),products);}
        catch(error){const rejected=new EnterpriseCycleError('delivery_review_required',error.message+
          ' If saved outputs are usable, finish this assessment with coverage partial or unmet, truthful failed/not_run checks, decision limited, summary of remaining limits, follow_ups: [], and delivery_product_refs selecting the usable previously recorded current paths. This retains unresolved review findings without claiming a clean review. Do not repeat review or rebuild usable outputs solely to seek a perfect verdict. Repair only a necessary usability defect or a material issue that you can verify against actual sources; reviewer opinions are not factual proof. Select only intended final deliverables; process products remain retained. Any changed selected bytes still require real recording under an execute action; never submit record with an assess action ID.');
          rejected.delivery_review=error.delivery_review;throw rejected;}
      }
      if(operation.operation==='assess'&&operation.decision==='limited'){
        const gaps=operation.checks.filter(check=>check.status!=='passed').map(check=>
          'Unresolved check '+check.description+' ('+check.status+'): '+check.explanation);
        if(requestedDelivery)for(const product of snapshot.active_products)
          if(!requestedDelivery.some(selected=>selected.path===product.path)&&!products.some(current=>current.path===product.path&&current.ref===product.ref))
            gaps.push('Registered product excluded from limited delivery because it is unavailable or has changed: '+product.path);
        if(config.researchRuntime?.deliveryReview?.enabled===true&&snapshot?.output_mode==='files'){
          const status=reviewStatus(operation.delivery_product_refs!==undefined?requestedDelivery:undefined);
          gaps.push(...status.missing_products.map(path=>'Product '+path+' has no completed independent review for its current version.'));
          gaps.push(...status.blocking_findings.map(item=>'Unresolved reviewer question '+item.id+' ('+item.path+'): '+item.description));
          gaps.push(...status.stale_reviews.map(item=>'Stale independent review '+item.receipt_ref+': '+item.products.map(product=>product.path).join(', ')));
          for(const receipt of receipts){
            if(receipt.tool_name==='agent_delegate'&&receipt.status==='failed')gaps.push('Delegated execution or review failed: '+receipt.ref+'. No successful review is claimed for that call.');
            for(const limitation of receipt.review?.not_checked??[])gaps.push('Independent review did not check: '+limitation);
          }
        }
        operation.summary=[operation.summary,...new Set(gaps)].join('\n');
      }
      const result=reduceEnterpriseCycle(snapshot??null,operation,host(),options);
      if(result.state.pending_action?.subtasks?.length)
        checkCapacity(resolveLimits({research_delegation_tasks:config.researchRuntime?.delegation?.maxTasks??capacities.research_question_count},
          {mode:runtimeLimitMode(capacities)}),'research_delegation_tasks',result.state.pending_action.subtasks.length,'items','research_plan');
      pending={key,call:{id:callId,hash:payloadHash,finding_ids:operation.operation==='record'?operation.findings.map(item=>item.id):[]},result};
      return await settle(pending);
    }catch(error){
      if(runtimeLimitMode(capacities)==='debug'&&error.capacity){
        if(error.capacity.mode==='debug')throw error;
        const detail=error.capacity;
        const dimension=({research_findings:'research_claim_count',research_questions:'research_question_count',
          research_objectives:'research_question_count',research_snapshot_bytes:'control_document_bytes',
          research_rounds:'research_question_count'})[detail.dimension]??detail.dimension;
        throw new CapacityExceeded({[dimension]:detail.limit},dimension,detail.actual,detail.unit,'research_cycle:'+detail.dimension,{mode:'debug'});
      }
      if(signal?.aborted)throw error;
      if(error.definiteRejected||error.capacity){pending=undefined;snapshot=committed?structuredClone(committed.snapshot):undefined;lastStatus=snapshot?.phase??'idle';}
      const code=error.code??'research_cycle_rejected';
      const message=error.capacity?'Configured research capacity was exceeded.':safeCodes[code]??
        (error instanceof EnterpriseCycleError?error.message:'Research checkpoint is not confirmed; recover the same request or correct the operation.');
      const diagnostic=error.product_mismatches;
      const text=diagnostic?message+'\n'+JSON.stringify({product_mismatches:diagnostic}):
        error.action_mismatch?message+'\n'+JSON.stringify({action_mismatch:error.action_mismatch}):
        error.delivery_review?message+'\n'+JSON.stringify({delivery_review:error.delivery_review}):message;
      lastRepair={code,message:text};
      return {content:[{type:'text',text}],details:{capability:'agent_research_cycle',ok:false,error:{code,message,
        ...(diagnostic?{product_mismatches:diagnostic}:{}),...(error.action_mismatch?{action_mismatch:error.action_mismatch}:{}),...(error.delivery_review?{delivery_review:error.delivery_review}:{}),...(error.capacity?{capacity:error.capacity}:{})}}};
    }finally{busy=false;activeSignal=undefined;}
  }
  let automaticDispatchCall;
  async function executeAndDispatch(callId,params,signal){
    await load();
    // A model retry receives a new SDK call ID. Match the frozen control input,
    // not that transport ID, when recovering this action's retained dispatch.
    const controlHash=hash(JSON.stringify(canonical(params)));
    const recovering=dispatches.get('dispatch:'+snapshot?.pending_action?.id)?.control_hash===controlHash;
    const reply=recovering?success():await execute(callId,params,signal);
    const action=snapshot?.pending_action;
    if(!reply.details?.ok||action?.kind!=='execute'||!action.subtasks?.length||
      reply.details.result.pending_action?.id!==action.id)return reply;
    const key='dispatch:'+action.id;
    let dispatch=dispatches.get(key);
    if(!dispatch){
      dispatch={status:'started',control_hash:controlHash};dispatches.set(key,dispatch);
      // Durable intent precedes native execution. A recovered incomplete intent
      // is reported; it never silently repeats potentially mutating child work.
      await persist(key+':started',snapshot,snapshot.phase,[],[],signal);
      automaticDispatchCall='auto-'+hash(action.id);
      let observed;
      try{observed=await dispatchSubtasks(automaticDispatchCall,structuredClone(action.subtasks),signal);}
      finally{automaticDispatchCall=undefined;}
      dispatch={status:'completed',control_hash:controlHash,result:observed};dispatches.set(key,dispatch);
    }
    // Retain execution state, without asserting child findings. The worker can
    // see this request before it admits the just-emitted tool-end observation.
    // Actual claims still require admitted references in record/assessment.
    if(dispatch.status==='completed')await persist(key+':completed',snapshot,snapshot.phase,[],[],signal);
    const current=success();
    current.details.result.delegation=dispatch.status==='completed'?structuredClone(dispatch.result):{
      isError:true,content:[{type:'text',text:'Automatic child execution was interrupted before its result checkpoint. Do not repeat it blindly. Record the missing result as a limitation or plan an explicit recovery.'}]};
    current.content=[{type:'text',text:JSON.stringify(current.details.result)}];
    return current;
  }
  return {
    async readState({includeReviewDetails=true}={}){
      await load();
      const status=config.researchRuntime?.deliveryReview?.enabled===true?reviewStatus():undefined;
      return structuredClone({phase:snapshot?.phase??'idle',round:snapshot?.round??0,
        pending_action:snapshot?.pending_action??null,next_action:action(),checkpoint:currentCheckpoint??null,
        update_pending:Boolean(pending),...(status?{delivery_review:includeReviewDetails?status:{ready:status.ready,
          selection_status:status.selection_status,required_count:status.required_products.length,missing_count:status.missing_products.length,
          stale_review_count:status.stale_reviews.length,blocking_count:status.blocking_findings.length,
          recovery:'Read overview.cycle.delivery_review for complete required, missing and stale paths and unresolved finding IDs.'}}:{})});
    },
    async delegationContext(jobs,{toolCallId,signal,reviewMode}={}){
      signal?.throwIfAborted();await load();
      const token=[...tokens].find(item=>item.toolCallId===toolCallId&&item.toolName==='agent_delegate');
      if(!token||!currentCheckpoint||token.action.id!==snapshot?.pending_action?.id)
        throw new EnterpriseCycleError('research_delegation_not_bound','Delegation requires an accepted current research action.');
      if(token.action.kind==='execute'&&(token.action.subtasks?.length||config.researchRuntime?.explicitSubtaskPlanning===true)&&toolCallId!==automaticDispatchCall)
        throw new EnterpriseCycleError('research_automatic_delegation_owned','The host owns this action’s automatic subtask batch. Do not start another batch. Recover an unconfirmed result by repeating the same research control request; otherwise record and assess the returned results.');
      if((reviewMode!==undefined&&reviewMode!=='delivery')||(reviewMode==='delivery'&&config.researchRuntime?.deliveryReview?.enabled!==true))
        throw new EnterpriseCycleError('research_review_not_enabled','Delivery review mode is not enabled for this accepted configuration.');
      if(token.action.kind!=='execute'&&!(token.action.kind==='assess'&&reviewMode==='delivery'))
        throw new EnterpriseCycleError('research_delegation_not_execution','Assessment permits only host-prepared read-only delivery review; ordinary child execution requires the next accepted execute action.');
      const accepted=snapshot.objectives.find(item=>item.id===token.action.objective_id);
      for(const job of jobs){
        if(!Array.isArray(job.questions)||!job.questions.length||job.questions.some(question=>!accepted.questions.includes(question)))
          throw new EnterpriseCycleError('research_branch_question_invalid','Each child needs questions copied from pending_action.questions. Plan newly discovered questions in an assessment before delegating them.');
        if(!Array.isArray(job.expected_outputs)||!job.expected_outputs.length||job.expected_outputs.some(value=>typeof value!=='string'||!value.trim()))
          throw new EnterpriseCycleError('research_branch_expectation_missing','Each child needs explicit expected_outputs describing the findings or evidence it must return.');
      }
      return structuredClone({owner:config.researchOwner,attempt_id:config.researchAttemptId,
        parent_action_id:token.action.id,parent_step_id:accepted.id,checkpoint:currentCheckpoint,...(reviewMode==='delivery'?{review_mode:'delivery'}:{})});
    },
    register(pi){
      pi.on?.('before_agent_start',event=>({systemPrompt:(event.systemPrompt??'')+'\n\n'+cycleGuidance+
        `\nControl entrances: plan using ${entrance('plan')}; record using ${entrance('record')}; assess using ${entrance('assess')}.`+
        (split?' The host binds the operation for each tool; do not include an operation field.':'')}));
      pi.on?.('tool_result',event=>{
        if(controlTools.has(event.toolName)&&event.details?.ok===false)return {isError:true};
        if(config.researchRuntime?.gracefulExecutionClosure===true&&event.isError===true&&
          ['bash','read','write','edit'].includes(event.toolName)&&snapshot?.pending_action?.kind==='execute')
          return {content:[...event.content,{type:'text',text:
            'Host closure guidance: keep the actual failure. If requested core outputs are already readable and usable, submit the usable draft for human review instead of repeatedly repairing a local checker. '+
            `Record action ${snapshot.pending_action.id} using ${entrance('record')}, outcome="limited", actual current product_refs and concrete limitations. `+
            `Then use the returned new assess action ID with ${entrance('assess')}, coverage partial/unmet, truthful failed/not_run checks, decision="limited", follow_ups: [] and usable delivery_product_refs. `+
            'A self-written validator does not need every check or literal to pass before a draft can be shared. Record unresolved numerical or consistency issues explicitly; repair a necessary opening/readability defect, not every advisory warning. '+
            'This does not override permissions, source/file identity, required persistence or valid receipts, and does not claim that absent or changed files were delivered.'}]};
      });
      const description='Commit a plan before execution, record actual host-receipted work, then assess it in a separate call. Each objective can span many model/tool turns. Checks and repair objectives govern completion. File record product_refs are actual relative file paths; returned refs are immutable inspected versions. No Authority evidence or extra model is created.';
      const producerDescription=config.researchRuntime?.gracefulExecutionClosure===true?
        ' For requested file production, declare objective.product_paths as the core final report/table relative paths. Separate producing readable files from advisory checks. Once the host observes those files, record their actual versions before more native producer work, then assess. Failed advisory checking or repair can be recorded partial and followed by an independent handoff that depends on production, not on all checks passing; finish with limitations. Do not require perfect validation logs or temporary files in product_paths.':'';
      const shapes={plan:'Plan fields: goal (string), output_mode (text or files), objectives (array), source_refs (array). Each objective uses id/purpose strings; questions/depends_on/expected_outputs/checks/input_refs/resolves arrays; mode execute or synthesis. Even one expected output is ["Source summary"], never a string.',
        record:'Record fields: action_id (current execute ID), outcome, findings (array), product_refs (array), limitations (array). Record returns a different pending assess action ID; copy that new ID for assessment.',
        assess:'Assess required top-level fields: action_id, coverage, checks, decision, summary (nonempty string), follow_ups (array, [] when none). Each check has description/status/refs/explanation. Optional delivery_product_refs selects final file paths from previously recorded products for deliver/limited; unrelated process files stay retained. Optional reflection contains discoveries/unresolved_questions/contradictions/next_step_reason, never the top-level summary.'};
      function parametersFor(operation){
        const original=operation?cycleOperationToolParameters[operation]:cycleToolParameters;
        if(config.researchRuntime?.explicitSubtaskPlanning!==true)return original;
        const schema=structuredClone(original);
        function visit(value){
          if(!value||typeof value!=='object')return;
          if(value.properties?.subtasks&&value.properties?.purpose){
            value.required=[...new Set([...value.required,'subtasks'])];
            value.properties.subtasks.description='Required execution arrangement. Declare substantial independent investigations as child tasks here before parent analysis; the host dispatches them automatically. Use [] for discovery, dependent production, tiny work or other parent-owned sequential work. Merely listing questions in one objective does not create children. '+
              value.properties.subtasks.description.replace(/^Optional /,'');
          }
          for(const child of Object.values(value))visit(child);
        }
        visit(schema);return schema;
      }
      for(const name of entrances){
        const operation=Object.keys(splitTools).find(key=>splitTools[key]===name);
        pi.registerTool({name,label:operation?`Research ${operation}`:'Advance enterprise research',
          parameters:parametersFor(operation),description:(operation?shapes[operation]+' '+description:description)+producerDescription+
            (config.researchRuntime?.explicitSubtaskPlanning===true?' Every planned or follow-up objective must explicitly include subtasks. Use a real child graph for independent investigations; use [] for parent-owned sequential work.':''),
          execute:operation?async(callId,params,signal)=>{
            let bound;
            try{bound=validateBoundCycleOperation(operation,params);}catch(error){
              if(!(error instanceof EnterpriseCycleError))throw error;
              signal?.throwIfAborted();attemptedCycle=true;
              lastRepair={code:error.code,message:error.message};
              return {content:[{type:'text',text:error.message}],details:{capability:'agent_research_cycle',ok:false,error:{code:error.code,message:error.message}}};
            }
            return executeAndDispatch(callId,bound,signal);
          }:executeAndDispatch});
      }},
    async beginTool({toolCallId,toolName,signal}){
      signal?.throwIfAborted();
      if(controlTools.has(toolName))throw new EnterpriseCycleError('research_control_not_execution','Research control calls cannot count as business execution.');
      attemptedCycle=true;await load();
      if(busy)throw new EnterpriseCycleError('research_cycle_busy','A research transition is being committed. Wait for its result before starting more tool work.');
      if(pending)throw new EnterpriseCycleError('research_update_not_confirmed','Recover the same unconfirmed research checkpoint before more tool work.');
      if(!snapshot?.pending_action){
        const message=snapshot?'The research cycle is settled. Present its actual result; do not start unplanned tool work.':
          `Commit ${entrance('plan')} before executing research tools. Use concrete objectives and completion checks; then execute the accepted action.`;
        lastRepair={code:'research_plan_required',message};throw new EnterpriseCycleError('research_plan_required',message);
      }
      const action=snapshot.pending_action,objective=snapshot.objectives.find(item=>item.id===action.objective_id);
      if(config.researchRuntime?.gracefulExecutionClosure===true&&objective?.product_paths?.length&&!tokens.size){
        let message;
        if(action.kind==='assess')message=`Producer files are already recorded. Commit assessment action ${action.id} before more native work. `+
          'Record unresolved quality issues as partial/failed checks; continue an independent accepted advisory or handoff objective, or finish limited. Do not submit record with an assess ID.';
        else {
          message=await producerOutputMessage(action,objective,signal);
          if(busy||pending||snapshot.pending_action?.id!==action.id)
            throw new EnterpriseCycleError('research_cycle_busy','The research action changed during output inspection. Wait for the committed transition and read the current action before native work.');
        }
        if(message){lastRepair={code:'research_product_checkpoint_required',message};
          throw new EnterpriseCycleError(lastRepair.code,message);}
      }
      const token=Object.freeze({toolCallId,toolName,action:structuredClone(snapshot.pending_action)});tokens.add(token);return token;
    },
    endTool(token,result,error){if(!token||!tokens.has(token))return;tokens.delete(token);
      const source=result?.details?.native_research_source?.source_ref;
      const status=error||result?.isError===true?'failed':'completed';
      const ref=source??'execution-receipt:'+hash(runId+'\0'+token.toolCallId+'\0'+status);
      if(source&&status==='completed')sources.add(source);
      if(token.action){const item={ref,action_id:token.action.id,attempt_id:config.researchAttemptId,status,tool_name:token.toolName,
        ...(status==='completed'&&token.toolName==='agent_delegate'&&isTrustedDeliveryReview(result?.details?.delivery_review)?{review:structuredClone(result.details.delivery_review)}:{})};
        const old=receipts.find(value=>value.ref===ref);if(old&&JSON.stringify(old)!==JSON.stringify(item))throw new Error('Execution receipt identity changed');
        if(!old)receipts.push(item);}
    },
    async completeTool(token,result,{signal}={}){
      const admitted=token&&tokens.has(token);
      this.endTool(token,result);
      signal?.throwIfAborted();
      if(!admitted||result?.isError===true||config.researchRuntime?.gracefulExecutionClosure!==true||
        !['bash','write','edit','agent_delegate'].includes(token.toolName)||tokens.size||busy||pending||
        token.action.id!==snapshot?.pending_action?.id||token.action.kind!=='execute')return result;
      const objective=snapshot.objectives.find(item=>item.id===token.action.objective_id);
      if(!objective?.product_paths?.length)return result;
      let message;
      try{message=await producerOutputMessage(token.action,objective,signal);}
      catch(error){
        signal?.throwIfAborted();
        // Preserve the actual successful tool result and expose a separate host
        // inspection failure. The normal admission check still guards new work.
        message=`Host output checkpoint inspection failed (${error.code??error.name??'Error'}): ${error.message??String(error)}. The original tool result is retained. `+
          'No output was registered or verified by this inspection. Use the current research action and report unresolved inspection limits.';
      }
      return message?{...result,content:[...(result.content??[]),{type:'text',text:message}]}:result;
    },
    async continuation(){await load();if(!attemptedCycle&&!snapshot&&!pending)return null;if(!pending&&terminal.has(snapshot?.phase))return null;
      const until=typeof config.deadlineAt==='string'?Date.parse(config.deadlineAt):config.deadlineAt;
      if(until!==undefined&&Date.now()>=until)throw new DOMException('Research deadline exceeded','TimeoutError');
      return pending?'Recover the same unconfirmed research checkpoint before new work; do not repeat source execution.':(lastRepair?lastRepair.message+' ':'')+action();},
    async continuationState(){const prompt=await this.continuation();return prompt?{prompt,actionId:snapshot?.pending_action?.id??pending?.key??'initialization',checkpoint:progressRevision}:null;},
    get status(){return Object.freeze({status:lastStatus,phase:snapshot?.phase??'idle',round:snapshot?.round??0,pending_action:snapshot?.pending_action??null});},
  };
}
