import test from 'node:test';
import assert from 'node:assert/strict';
import {createEnterpriseResearchController} from '../../src/capstone_agent/resources/enterprise-research-runtime.mjs';
const objective={id:'sum',purpose:'Verify total',questions:['What is total?'],depends_on:[],expected_outputs:['report'],checks:['sum matches'],mode:'execute',input_refs:[],resolves:[]};
const plan={operation:'plan',goal:'Correct report',output_mode:'files',objectives:[objective],source_refs:['material:source']};
function harness(extra={}){
  let revision=1,state={goal:'Prior goal',claims:[{claim_id:'old',statement:'Keep earlier claim',status:'pending',refs:[]}],notes:[{note_id:'human',text:'Keep earlier note',refs:[]}]};
  const tools=new Map(),hooks=new Map(),versions=new Map(),inspections=[];let tool,rejectNext=false,unknownNext=false,available=true,failProjection=false,nextInspection,inspectionError;const requests=[],accepted=new Map(),events=[];
  const config={researchTaskId:'task',researchAttemptId:'attempt',researchOwner:{thread_id:'thread',work_id:'work',research_id:'research',goal_revision:1},researchSources:['material:source'],
    researchRuntime:{limits:{maxRounds:10,maxFindings:100,maxQuestions:100,snapshotBytes:16*1024*1024}},...extra};
  const ports={config,dispatchSubtasks:extra.dispatchSubtasks,readResearch:async()=>({research_revision:revision,state:structuredClone(state)}),
    commitResearch:async(id,request)=>{requests.push({id,request:structuredClone(request)});if(accepted.has(id)){assert.deepEqual(request,accepted.get(id).request);return accepted.get(id).result;}
      if(rejectNext){rejectNext=false;return {details:{ok:false,result:{status:'rejected',code:'research_reference_not_admitted'}}};}
      if(unknownNext){unknownNext=false;return {details:{ok:false,result:{status:'not_confirmed'}}};}
      assert.equal(request.expected_revision,revision);const changes=request.changes;
      for(const note of changes.notes){assert.ok(!state.notes.some(old=>old.note_id===note.note_id),'one append-only checkpoint per accepted call');}
      const claims=new Map(state.claims.map(c=>[c.claim_id,c]));for(const claim of changes.claims)claims.set(claim.claim_id,claim);
      state={...state,...changes,notes:[...state.notes,...changes.notes],claims:[...claims.values()]};revision++;
      const result={details:{ok:true,result:{status:'committed',receipt:{research_revision:revision}}}};accepted.set(id,{request:structuredClone(request),result});return result;},
    inspectProducts:async({productRefs})=>{const wait=nextInspection;nextInspection=undefined;if(wait)await wait;if(inspectionError){const error=inspectionError;inspectionError=undefined;throw error;}inspections.push([...productRefs]);return {ready:available,products:available?productRefs.map(path=>({path,sha256:versions.get(path)??'b'.repeat(64),bytes:10})):[],limitations:available?[]:['Report is missing']};},
    onProgress:e=>{if(failProjection){failProjection=false;throw Error('Projection interrupted');}events.push(e);}};
  const make=()=>{const controller=createEnterpriseResearchController(ports);controller.register({on(name,fn){hooks.set(name,fn);},registerTool(t){tool=t;tools.set(t.name,t);}});return controller;};
  let controller=make();return {get controller(){return controller;},call:(id,args,signal)=>tool.execute(id,args,signal),config,requests,events,tools,hooks,get state(){return state;},
    reject(){rejectNext=true;},unknown(){unknownNext=true;},missing(value=true){available=!value;},version(path,sha){versions.set(path,sha);},inspections,restore(){controller=make();},failProjection(){failProjection=true;},
    pauseInspection(){let release;nextInspection=new Promise(resolve=>{release=resolve;});return ()=>release();},
    failInspection(error){inspectionError=error;},
    async observe(id='read'){const token=await controller.beginTool({toolCallId:id,toolName:'read'});controller.endTool(token,{details:{native_research_source:{source_ref:'native-observation:'+id}}});return 'native-observation:'+id;}};
}
const result=r=>{assert.equal(r.details.ok,true,r.content?.[0]?.text);return r.details.result;};

test('committed subtasks dispatch automatically once and completed results survive replay',async()=>{
  let calls=0,h;
  h=harness({applicationPolicy:{allowed_tools:['agent_research_cycle','agent_delegate']},dispatchSubtasks:async(id,tasks)=>{
    calls++;assert.ok(h.state.notes.length>1,'dispatch starts only after committed intent');
    const token=await h.controller.beginTool({toolCallId:id,toolName:'agent_delegate'});
    const observed={content:[{type:'text',text:'child answer'}],details:{children:[{status:'completed',answer:'10'}],native_research_source:{source_ref:'native-observation:auto'}}};
    h.controller.endTool(token,observed);return observed;
  }});
  const request={...plan,objectives:[{...objective,subtasks:[{id:'total',title:'Total',instruction:'Compute total',
    questions:objective.questions,expected_outputs:['Total with source'],depends_on:[]}]}]};
  const first=result(await h.call('auto-plan',request));
  assert.equal(calls,1);assert.equal(first.delegation.details.children[0].answer,'10');
  assert.ok(first.execution_receipts.some(x=>x.ref==='native-observation:auto'));
  const dispatchWrite=h.requests.find(item=>item.request.changes.notes.some(note=>
    note.note_id.startsWith('runtime.dispatch.')&&JSON.parse(note.text).dispatches.some(([,value])=>value.status==='completed')));
  assert.deepEqual(dispatchWrite.request.changes.notes[0].refs,[],
    'retaining the batch is not a claim: its tool-end observation has not yet been admitted by the worker');
  result(await h.call('auto-plan',request));assert.equal(calls,1);
  h.restore();const replay=result(await h.call('auto-plan',request));assert.equal(calls,1);
  assert.equal(replay.delegation.details.children[0].answer,'10');
});

for(const uncertain of [false,true])test(`manual delegation cannot repeat an automatic batch (${uncertain?'unconfirmed':'confirmed'} result)`,async()=>{
  let h,calls=0;
  h=harness({applicationPolicy:{allowed_tools:['agent_research_cycle','agent_delegate']},dispatchSubtasks:async(id,tasks)=>{
    calls++;
    const token=await h.controller.beginTool({toolCallId:id,toolName:'agent_delegate'});
    await h.controller.delegationContext(tasks,{toolCallId:id});
    h.controller.endTool(token,{content:[{type:'text',text:'child complete'}],details:{}});
    if(uncertain)h.unknown();
    return {content:[{type:'text',text:'retained child result'}],details:{children:[]}};
  }});
  const jobs=[{id:'total',title:'Total',instruction:'Compute total',questions:objective.questions,expected_outputs:['Total'],depends_on:[]}];
  const request={...plan,objectives:[{...objective,subtasks:jobs}]};
  if(uncertain)await assert.rejects(h.call('automatic',request),/not confirmed/);
  else result(await h.call('automatic',request));
  await assert.rejects(async()=>{
    const token=await h.controller.beginTool({toolCallId:'manual-repeat',toolName:'agent_delegate'});
    try{await h.controller.delegationContext(jobs,{toolCallId:'manual-repeat'});}
    finally{h.controller.endTool(token,{isError:true,content:[]});}
  },error=>error.code==='research_automatic_delegation_owned');
  const recovered=result(await h.call('automatic',request));
  assert.equal(calls,1);assert.equal(recovered.delegation.content[0].text,'retained child result');
  h.restore();
  await assert.rejects(async()=>{
    const token=await h.controller.beginTool({toolCallId:'manual-after-restore',toolName:'agent_delegate'});
    try{await h.controller.delegationContext(jobs,{toolCallId:'manual-after-restore'});}
    finally{h.controller.endTool(token,{isError:true,content:[]});}
  },error=>error.code==='research_automatic_delegation_owned');
});

test('unavailable automatic executor rejects the plan before committing',async()=>{
  const h=harness();const response=await h.call('no-executor',{...plan,objectives:[{...objective,subtasks:[
    {id:'total',title:'Total',instruction:'Compute',questions:objective.questions,expected_outputs:['Total'],depends_on:[]}]}]});
  assert.equal(response.details.ok,false);assert.equal(h.requests.length,0);
});

test('explicit planning publication requires a subtask decision but permits empty serial and producer graphs',async()=>{
  const h=harness({researchRuntime:{explicitSubtaskPlanning:true},applicationPolicy:{allowed_tools:['agent_research_plan','agent_research_record','agent_research_assess']}});
  const schema=h.tools.get('agent_research_plan').parameters.properties.objectives.items;
  assert.ok(schema.required.includes('subtasks'));
  assert.match(schema.properties.subtasks.description,/independent investigations/i);
  const {operation,...input}=plan;
  const missing=await h.tools.get('agent_research_plan').execute('missing-graph',input);
  assert.equal(missing.details.ok,false);assert.equal(h.requests.length,0);
  const accepted=result(await h.tools.get('agent_research_plan').execute('explicit-serial',{
    ...input,objectives:[{...objective,subtasks:[]},{...objective,id:'produce',depends_on:['sum'],product_paths:['report.md'],subtasks:[]}]}));
  assert.equal(accepted.pending_action.objective_id,'sum');
  assert.deepEqual(accepted.pending_action.subtasks,[]);
  const token=await h.controller.beginTool({toolCallId:'undeclared-child',toolName:'agent_delegate'});
  await assert.rejects(h.controller.delegationContext([{questions:objective.questions,expected_outputs:['Total']}],{toolCallId:'undeclared-child'}),
    error=>error.code==='research_automatic_delegation_owned');
  h.controller.endTool(token,{isError:true,content:[]});
  const legacy=harness();
  assert.ok(!legacy.tools.get('agent_research_cycle').parameters.oneOf[0].properties.objectives.items.required.includes('subtasks'));
  result(await legacy.call('legacy',plan));
});

test('interrupted automatic dispatch is retained and never silently restarted on recovery',async()=>{
  let calls=0;
  const h=harness({applicationPolicy:{allowed_tools:['agent_research_cycle','agent_delegate']},dispatchSubtasks:async()=>{
    calls++;throw Error('worker interrupted');
  }});
  const request={...plan,objectives:[{...objective,subtasks:[{id:'total',title:'Total',instruction:'Compute',
    questions:objective.questions,expected_outputs:['Total'],depends_on:[]}]}]};
  await assert.rejects(h.call('interrupted-plan',request),/worker interrupted/);
  h.restore();const replay=result(await h.call('interrupted-plan',request));
  assert.equal(calls,1);assert.equal(replay.delegation.isError,true);
  assert.match(replay.delegation.content[0].text,/interrupted/);
  const token=await h.controller.beginTool({toolCallId:'recovery-read',toolName:'read'});
  h.controller.endTool(token,{details:{native_research_source:{source_ref:'native-observation:recovery'}}});
});

test('combined ready graphs cannot exceed task capacity before checkpoint or child launch',async()=>{
 let calls=0;
 const h=harness({applicationPolicy:{allowed_tools:['agent_research_cycle','agent_delegate']},
   researchRuntime:{batchReadyInvestigations:true,delegation:{maxTasks:1}},dispatchSubtasks:async()=>{calls++;}});
 const branch=id=>({...objective,id,subtasks:[{id:'check',title:id,instruction:'Check source',
   questions:objective.questions,expected_outputs:['Observation'],depends_on:[]}]});
 const reply=await h.call('too-many-ready',{...plan,objectives:[branch('one'),branch('two')]});
 assert.equal(reply.details.ok,false);assert.equal(calls,0);assert.equal(h.requests.length,0);
 assert.equal(reply.details.error.capacity.actual,2);assert.equal(reply.details.error.capacity.limit,1);
});

test('an unconfirmed result checkpoint is confirmed before replay exposes child results',async()=>{
  let calls=0,h;
  h=harness({applicationPolicy:{allowed_tools:['agent_research_cycle','agent_delegate']},dispatchSubtasks:async()=>{
    calls++;h.unknown();return {content:[{type:'text',text:'retained result'}],details:{children:[]}};
  }});
  const request={...plan,objectives:[{...objective,subtasks:[{id:'total',title:'Total',instruction:'Compute',
    questions:objective.questions,expected_outputs:['Total'],depends_on:[]}]}]};
  await assert.rejects(h.call('uncertain-result',request),/not confirmed/);
  const replay=result(await h.call('uncertain-result',request));
  assert.equal(calls,1);assert.equal(replay.delegation.content[0].text,'retained result');
  const newToolCall=result(await h.call('model-retry-with-new-call-id',request));
  assert.equal(calls,1);assert.equal(newToolCall.delegation.content[0].text,'retained result');
  const saved=h.state.notes.map(note=>{try{return JSON.parse(note.text);}catch{return {};}});
  assert.ok(saved.some(note=>note.dispatches?.some(([,value])=>value.status==='completed')));
});
async function start(h,override={}){return result(await h.call('plan',{...plan,...override})).pending_action;}
const record=(action,refs=[],products=['report.md'])=>({operation:'record',action_id:action.id,outcome:'completed',findings:refs.length?[{id:'total',text:'Actual total agrees',status:'supported',refs}]:[],product_refs:products,limitations:[]});
const assess=(action,refs,decision='deliver')=>({operation:'assess',action_id:action.id,coverage:[{objective_id:'sum',status:'met',refs,explanation:'Compared actual result'}],
  checks:[{description:'sum matches',status:'passed',refs,explanation:'Observed agreement'}],decision,summary:'Report total agrees',follow_ups:[]});
async function prepare(h,mode='files'){const action=await start(h,{output_mode:mode});const ref=await h.observe();return {ref,action:result(await h.call('record',record(action,[ref],mode==='text'?[]:['report.md']))).pending_action};}

test('next execute feedback offers exact accepted question batches without mandatory delegation or changing state',async()=>{
 const h=harness();const reply=result(await h.call('plan',plan));
 assert.match(reply.next_action,/independent questions in pending_action.questions/i);
 assert.match(reply.next_action,/one agent_delegate batch/);
 assert.match(reply.next_action,/parent owns shared outputs/i);
 assert.match(reply.next_action,/keep dependent work sequential/i);
 assert.deepEqual(reply.pending_action.questions,objective.questions);
 assert.equal(h.requests.length,1);
});

test('failed local tool offers current limited-record route only for the accepted draft profile',async()=>{
 for(const enabled of [false,true]){
  const h=harness({researchRuntime:{gracefulExecutionClosure:enabled}});const action=await start(h);
  const before=h.requests.length;const event={toolName:'bash',isError:true,content:[{type:'text',text:'Local custom checker failed'}],details:{marker:'actual'}};
  const feedback=h.hooks.get('tool_result')(event);
  if(!enabled)assert.equal(feedback,undefined);
  else {
   const text=feedback.content.at(-1).text;
   assert.match(text,/usable draft.*human review/i);assert.ok(text.includes(action.id));
   assert.match(text,/outcome="limited"/);assert.match(text,/decision="limited"/);
   assert.match(text,/not.*every.*literal/i);
   assert.deepEqual(feedback.content[0],event.content[0]);assert.equal(feedback.isError,undefined,'actual error status is never rewritten');
   assert.equal(h.hooks.get('tool_result')({...event,isError:false}),undefined);
  }
  assert.equal(h.requests.length,before,'feedback does not mutate research state or create a retry');
 }
});

test('observed declared producer files require a real record before further native work, without a quality verdict',async()=>{
 for(const enabled of [false,true]){
  const h=harness({researchRuntime:{gracefulExecutionClosure:enabled}});h.missing();
  const execute=await start(h,{objectives:[{...objective,product_paths:['report.md']}]});
  const writing=await h.controller.beginTool({toolCallId:'produce',toolName:'write'});
  h.controller.endTool(writing,{details:{native_research_source:{source_ref:'native-observation:produced'}}});h.missing(false);
  if(!enabled){assert.ok(await h.controller.beginTool({toolCallId:'legacy-check',toolName:'bash'}));continue;}
  await assert.rejects(h.controller.beginTool({toolCallId:'unbounded-checker',toolName:'bash'}),error=>{
   assert.equal(error.code,'research_product_checkpoint_required');assert.ok(error.message.includes(execute.id));
   assert.match(error.message,/report.md/);assert.match(error.message,new RegExp('b'.repeat(64)));
   assert.match(error.message,/not.*quality/i);return true;
  });
  assert.equal(h.controller.status.pending_action.id,execute.id);assert.equal(h.requests.length,1,'file observation is not an automatic model-authored commit');
  const reply=result(await h.call('record-produced',record(execute,['native-observation:produced'])));
  assert.equal(reply.pending_action.kind,'assess');
  await assert.rejects(h.controller.beginTool({toolCallId:'check-before-assess',toolName:'bash'}),{code:'research_product_checkpoint_required'});
  assert.equal(result(await h.call('limited',{...assess(reply.pending_action,[],'limited'),coverage:[{objective_id:'sum',status:'partial',refs:[],explanation:'Checks deferred for human review'}],checks:[]})).status,'limited');
 }
});

test('producer completion returns the checkpoint before another rejected model/tool turn',async()=>{
 const h=harness({researchRuntime:{gracefulExecutionClosure:true}});h.missing();
 const execute=await start(h,{objectives:[{...objective,product_paths:['report.md']}]});
 const token=await h.controller.beginTool({toolCallId:'produce',toolName:'write'});h.missing(false);
 const actual={content:[{type:'text',text:'Saved report.md'}],details:{native_research_source:{source_ref:'native-observation:produced'}}};
 const reply=await h.controller.completeTool(token,actual);
 assert.deepEqual(reply.content[0],actual.content[0]);assert.equal(reply.isError,undefined);
 assert.match(reply.content.at(-1).text,/Observed producer output checkpoint/);
 assert.ok(reply.content.at(-1).text.includes(execute.id));assert.match(reply.content.at(-1).text,/not a quality verdict/);
 assert.equal(h.requests.length,1,'output feedback never records or assesses on behalf of the model');
 const recorded=result(await h.call('record-produced',record(execute,['native-observation:produced'])));
 assert.equal(recorded.pending_action.kind,'assess');
 assert.match(recorded.next_action,/before more native work/);
 assert.match(recorded.next_action,/follow.up/i);
 assert.equal(result(await h.call('limited',{...assess(recorded.pending_action,[],'limited'),
  coverage:[{objective_id:'sum',status:'partial',refs:[],explanation:'Quality checks deferred for human review'}],checks:[]})).status,'limited');
});

test('output feedback leaves old profiles, undeclared outputs and incomplete production unchanged',async()=>{
 for(const [enabled,declared,available] of [[false,true,true],[true,false,true],[true,true,false]]){
  const h=harness({researchRuntime:{gracefulExecutionClosure:enabled}});h.missing();
  await start(h,{objectives:[{...objective,...(declared?{product_paths:['report.md']}: {})}]});
  const token=await h.controller.beginTool({toolCallId:'produce',toolName:'write'});h.missing(!available);
  const actual={content:[{type:'text',text:'Actual output'}],details:{}};
  assert.equal(await h.controller.completeTool(token,actual),actual);
  assert.equal(h.requests.length,1);
 }
});

test('output inspection respects cancellation and cannot advise a superseded action',async()=>{
 const h=harness({researchRuntime:{gracefulExecutionClosure:true}});h.missing();
 const action=await start(h,{objectives:[{...objective,product_paths:['report.md']}]});
 const token=await h.controller.beginTool({toolCallId:'produce',toolName:'write'});h.missing(false);
 const release=h.pauseInspection();
 const actual={content:[{type:'text',text:'Saved report.md'}],details:{}};
 const reply=h.controller.completeTool(token,actual);
 await Promise.resolve();await Promise.resolve();
 result(await h.call('record',record(action,[])));
 release();assert.equal(await reply,actual,'late inspection cannot direct the model to the old execute ID');
 const cancelled=new AbortController();cancelled.abort();
 await assert.rejects(h.controller.completeTool(undefined,actual,{signal:cancelled.signal}),{name:'AbortError'});
});

test('parallel completion waits for all native work and preserves actual inspection errors',async()=>{
 const h=harness({researchRuntime:{gracefulExecutionClosure:true}});h.missing();
 await start(h,{objectives:[{...objective,product_paths:['report.md']}]});
 const first=await h.controller.beginTool({toolCallId:'first',toolName:'write'});
 const second=await h.controller.beginTool({toolCallId:'second',toolName:'bash'});h.missing(false);
 const actual={content:[{type:'text',text:'Actual saved file'}],details:{native_research_source:{source_ref:'native-observation:first'}}};
 const before=h.inspections.length;
 assert.equal(await h.controller.completeTool(first,actual),actual);assert.equal(h.inspections.length,before);
 h.failInspection(Object.assign(new Error('Selected output changed during inspection'),{code:'research_product_changed'}));
 const secondResult={...actual,details:{native_research_source:{source_ref:'native-observation:second'}}};
 const warned=await h.controller.completeTool(second,secondResult);
 assert.equal(warned.details,secondResult.details);assert.equal(warned.isError,undefined);assert.deepEqual(warned.content[0],actual.content[0]);
 assert.match(warned.content.at(-1).text,/research_product_changed.*Selected output changed during inspection/);
 assert.match(warned.content.at(-1).text,/No output was registered or verified/);
 assert.equal(h.requests.length,1);
});

test('producer path declaration rejects traversal rather than guessing output paths',async()=>{
 for(const path of ['../report.html','/private/report.html','data/../report.html','data\\report.html']){
  const h=harness({researchRuntime:{gracefulExecutionClosure:true}});
  assert.equal((await h.call('invalid',{...plan,objectives:[{...objective,product_paths:[path]}]})).details.ok,false);
  assert.equal(h.requests.length,0);
 }
});

test('delayed producer inspection cannot admit native work after a concurrent action transition',async()=>{
 const h=harness({researchRuntime:{gracefulExecutionClosure:true}});h.missing();
 const action=await start(h,{objectives:[{...objective,product_paths:['report.md']}]});
 const release=h.pauseInspection();const admission=h.controller.beginTool({toolCallId:'delayed',toolName:'write'});
 await Promise.resolve();await Promise.resolve();
 const settled=result(await h.call('failed-record',{...record(action,[],[]),outcome:'failed',findings:[],limitations:['Actual production could not complete.']}));
 release();await assert.rejects(admission,{code:'research_cycle_busy'});
 assert.equal(h.controller.status.pending_action.id,settled.pending_action.id);
 assert.equal(h.controller.status.pending_action.kind,'assess');
});

test('failed independent review can close limited with usable bound products and durable concrete gaps',async()=>{
 const h=harness({researchRuntime:{deliveryReview:{enabled:true}}});
 const execute=await start(h),ref=await h.observe();
 const token=await h.controller.beginTool({toolCallId:'failed-review',toolName:'agent_delegate'});
 h.controller.endTool(token,{isError:true});
 const action=result(await h.call('record',record(execute,[ref]))).pending_action;
 const rejected=await h.call('clean-delivery',assess(action,[ref]));
 assert.equal(rejected.details.error.code,'delivery_review_required');
 assert.match(rejected.content[0].text,/partial.*limited/i);
 const closed=result(await h.call('limited-delivery',{...assess(action,[ref],'limited'),
  coverage:[{objective_id:'sum',status:'partial',refs:[ref],explanation:'Usable saved report; review failed'}],
  checks:[{description:'sum matches',status:'failed',refs:[],explanation:'Independent check did not complete'}],
  summary:'Saved report is provided with limitations.',delivery_product_refs:['report.md']}));
 assert.equal(closed.status,'limited');assert.equal(await h.controller.continuation(),null);
 const saved=JSON.parse(h.state.notes.at(-1).text);
 assert.equal(saved.snapshot.delivery_products[0].path,'report.md');
 assert.match(saved.snapshot.limitations.join('\n'),/report.md.*no completed independent review/i);
 assert.match(saved.snapshot.limitations.join('\n'),/failed.*execution-receipt/i);
 assert.match(saved.snapshot.limitations.join('\n'),/Independent check did not complete/);
 assert.ok(saved.receipts.some(receipt=>receipt.tool_name==='agent_delegate'&&receipt.status==='failed'&&!receipt.review));
 h.restore();assert.equal(await h.controller.continuation(),null);
});

test('assessment exposes pending question scopes and explicit operation without changing their order',async()=>{
 const h=harness();const later={...objective,id:'compare',purpose:'Explain the difference',questions:['Why does it differ?'],depends_on:['sum']};
 const active=await start(h,{objectives:[objective,later]});const ref=await h.observe();
 const reply=result(await h.call('record',record(active,[ref])));
 assert.match(reply.next_action,/operation="assess"/);
 assert.deepEqual(reply.planning_context.pending_objectives.map(item=>item.id),['compare']);
 assert.deepEqual(reply.planning_context.pending_objectives[0].questions,later.questions);
 assert.deepEqual(reply.planning_context.ready_if_current_met.map(item=>item.id),['compare']);
 assert.deepEqual(reply.planning_context.ready_if_current_met[0].expected_outputs,later.expected_outputs);
 assert.deepEqual(reply.planning_context.findings,[{id:'total',text:'Actual total agrees',status:'supported',refs:[ref]}]);
 reply.planning_context.pending_objectives[0].questions.push('Caller mutation');
 const replay=result(await h.call('record',record(active,[ref])));
 assert.deepEqual(replay.planning_context.pending_objectives[0].questions,later.questions);
});

test('preserves earlier notes and claims; exact accepted-call replay has no new commit or progress',async()=>{
 const h=harness();const action=await start(h);const before=h.requests.length;
 result(await h.call('plan',plan));assert.equal(h.requests.length,before);assert.equal(h.events.length,1);
 assert.equal((await h.call('plan',{...plan,goal:'Changed'})).details.error.code,'research_call_identity_changed');
 assert.equal(h.state.notes[0].text,'Keep earlier note');assert.equal(h.state.claims[0].statement,'Keep earlier claim');assert.ok(action.id.startsWith('cycle-'));
});
test('actual receipt binding is captured before tool execution and never taken from model input',async()=>{
 const h=harness();await assert.rejects(h.controller.beginTool({toolCallId:'pre-plan',toolName:'read'}),/plan/i);const action=await start(h);
 assert.equal((await h.call('fake',record(action,['native-observation:old']))).details.ok,false);
 const ref=await h.observe();result(await h.call('real',record(action,[ref])));
 const checkpoint=JSON.parse(h.state.notes.at(-1).text);assert.equal(checkpoint.receipts.length,1);assert.equal(checkpoint.receipts[0].action_id,action.id);
});
test('text-only output completes with real observations and no invented file',async()=>{
 const h=harness();const {ref,action}=await prepare(h,'text');assert.equal(result(await h.call('assess',assess(action,[ref]))).status,'done');
 assert.equal(await h.controller.continuation(),null);h.restore();assert.equal(await h.controller.continuation(),null);assert.equal(h.controller.status.status,'done');
});
test('missing files remain repairable without admitting a failed record',async()=>{
 const h=harness();const action=await start(h);const ref=await h.observe();h.missing();assert.equal((await h.call('absent',record(action,[ref]))).details.error.code,'research_products_unavailable');
 assert.equal(h.controller.status.pending_action.id,action.id);h.missing(false);result(await h.call('saved',record(action,[ref])));
});
test('done and blocked are not terminal until the exact final checkpoint is confirmed',async()=>{
 for(const decision of ['deliver','blocked']){const h=harness();const {ref,action}=await prepare(h);h.unknown();
 assert.equal((await h.call('terminal',assess(action,[ref],decision))).details.ok,false);assert.notEqual(await h.controller.continuation(),null);
 const request=h.requests.at(-1);assert.equal(result(await h.call('different-call',assess(action,[ref],decision))).status,decision==='deliver'?'done':'blocked');
 assert.deepEqual(h.requests.at(-1),request);assert.equal(await h.controller.continuation(),null);}
});
test('definite init rejection keeps repair intent; new call identity can correct it',async()=>{
 const h=harness();assert.equal(await h.controller.continuation(),null);h.reject();assert.equal((await h.call('bad',plan)).details.ok,false);
 assert.match(await h.controller.continuation(),/source|plan/i);result(await h.call('corrected',plan));assert.notEqual(h.requests[0].id,h.requests[1].id);
});
test('definite record rejection restores admitted action and preserves actual receipt for correction',async()=>{
 const h=harness();const action=await start(h),ref=await h.observe();h.reject();assert.equal((await h.call('bad',record(action,[ref]))).details.ok,false);
 assert.equal(h.controller.status.pending_action.id,action.id);result(await h.call('corrected',record(action,[ref])));
});
test('unconfirmed init recovers original frozen request without changing plan',async()=>{
 const h=harness();h.unknown();assert.equal((await h.call('init',plan)).details.ok,false);const initial=h.requests[0];
 result(await h.call('different',{...plan,goal:'Must not replace pending'}));assert.deepEqual(h.requests[1],initial);assert.equal(h.state.notes.length,2);
});
test('cancellation and configured checkpoint overflow cannot commit a plan',async()=>{
 const h=harness();const controller=new AbortController();controller.abort();await assert.rejects(h.call('cancelled',plan,controller.signal));assert.equal(h.requests.length,0);
 const small=harness({runtimeLimits:{research_text_chars:100}});const failed=await small.call('capacity',plan);assert.equal(failed.details.error.capacity.dimension,'research_text_chars');assert.equal(small.requests.length,0);
});
test('debug reducer capacity is fatal typed feedback, not a model repair result',async()=>{
 const h=harness({runtimeLimitMode:'debug',runtimeLimits:{research_text_chars:100}});
 await assert.rejects(h.call('debug-capacity',plan),error=>error.capacity?.mode==='debug'&&error.capacity.dimension==='research_text_chars');
 assert.equal(h.requests.length,0);
 const small=harness({runtimeLimitMode:'debug',researchRuntime:{limits:{maxRounds:10,maxFindings:100,maxQuestions:1,snapshotBytes:16777216}}});
 const oversized={...plan,objectives:[{...objective,questions:['First?','Second?']}]};
 await assert.rejects(small.call('debug-questions',oversized),error=>error.capacity?.mode==='debug'&&error.capacity.dimension==='research_question_count');
 assert.equal(small.requests.length,0);
});
test('Unicode checkpoints beyond 16k use configured budgets and append only deltas',async()=>{
 const h=harness();const text='研究🙂'.repeat(9000);result(await h.call('plan',{...plan,goal:text}));const first=h.requests[0].request.changes.notes[0];
 assert.ok(first.text.length>16384);const ref=await h.observe();result(await h.call('record',record(h.controller.status.pending_action,[ref])));
 assert.equal(h.requests[1].request.changes.notes.length,1);assert.equal(h.state.notes.length,3);
});
test('request and aggregate view capacity errors identify bytes and commit nothing',async()=>{
 for(const dimension of ['research_request_bytes','research_response_bytes']){const h=harness({runtimeLimits:{[dimension]:100}});const failed=await h.call('capacity',plan);
 assert.equal(failed.details.error.capacity.dimension,dimension);assert.equal(failed.details.error.capacity.unit,'bytes');assert.equal(h.requests.length,0);}
});
test('attempted repair obeys deadline while untouched chat has no continuation',async()=>{
 const h=harness({deadlineAt:Date.now()-1});assert.equal(await h.controller.continuation(),null);await h.call('invalid',{});await assert.rejects(h.controller.continuation(),{name:'TimeoutError'});
});
test('confirmed checkpoint recovers interrupted progress publication without repeating work or writes',async()=>{
 const h=harness();h.failProjection();assert.equal((await h.call('plan',plan)).details.ok,false);assert.equal(h.requests.length,1);assert.equal(h.events.length,0);
 const replay=result(await h.call('plan',plan));assert.equal(h.requests.length,1);assert.equal(h.events.length,1);assert.equal(h.events[0].action_id,replay.pending_action.id);
 const note=JSON.parse(h.state.notes.at(-1).text);assert.deepEqual(note.cycleCall.progress[0],{action_id:replay.pending_action.id,progress:h.events[0].progress});
 result(await h.call('plan',plan));assert.equal(h.events.length,1);
});
test('parallel native work must settle before recording or assessment; rejection is repairable',async()=>{
 const h=harness();const action=await start(h),ref=await h.observe();const writing=await h.controller.beginTool({toolCallId:'still-writing',toolName:'write'});
 assert.equal((await h.call('early-record',record(action,[ref]))).details.error.code,'research_execution_pending');
 assert.equal(h.controller.status.phase,'executing');h.controller.endTool(writing,{details:{native_research_source:{source_ref:'native-observation:write'}}});
 const assessment=result(await h.call('settled-record',record(action,[ref]))).pending_action;
 const checking=await h.controller.beginTool({toolCallId:'still-checking',toolName:'read'});
 assert.equal((await h.call('early-assess',assess(assessment,[ref]))).details.error.code,'research_execution_pending');
 h.controller.endTool(checking,{details:{native_research_source:{source_ref:'native-observation:check'}}});
 assert.equal(result(await h.call('settled-assess',assess(assessment,[ref]))).status,'done');
});

const splitNames=['agent_research_plan','agent_research_record','agent_research_assess'];
test('stale metrics diagnostic preserves valid outputs and only explicit inspected repair can complete delivery',async()=>{
 const h=harness(),paths=['report.html','metrics.csv','daily.csv','work/metrics.json'];
 const initial=await start(h),ref=await h.observe();
 const recorded=result(await h.call('all-products',record(initial,[ref],paths)));
 const before=JSON.parse(h.state.notes.at(-1).text).snapshot;
 h.version('work/metrics.json','c'.repeat(64));
 const commits=h.requests.length,progress=h.events.length;
 const rejected=await h.call('stale-delivery',assess(recorded.pending_action,[ref]));
 assert.equal(rejected.details.error.code,'research_product_version_mismatch');
 assert.equal(h.requests.length,commits);assert.equal(h.events.length,progress);
 assert.deepEqual(h.inspections.at(-1),paths,'The collector inspects every active product, including unchanged files');
 const diagnostic=rejected.details.error.product_mismatches;
 assert.equal(diagnostic.total,1);assert.equal(diagnostic.truncated,false);
 assert.equal(diagnostic.products[0].path,'work/metrics.json');assert.equal(diagnostic.products[0].status,'changed');
 assert.equal(diagnostic.products[0].registered_ref,before.active_products[3].ref);
 assert.notEqual(diagnostic.products[0].current_ref,before.active_products[3].ref);
 assert.match(rejected.content[0].text,/work\/metrics.json/);assert.match(rejected.content[0].text,/follow-up action/);
 assert.match(rejected.content[0].text,/Re-registration does not establish content quality/);
 assert.deepEqual(JSON.parse(h.state.notes.at(-1).text).snapshot,before,'Rejection cannot change the accepted snapshot');
 const repair={...objective,id:'rebind',purpose:'Verify and register current metrics bytes'};
 const next=result(await h.call('accept-repair',{...assess(recorded.pending_action,[ref],'continue'),follow_ups:[repair]}));
 const repairRef=await h.observe('verify-current-metrics');
 const repaired=result(await h.call('record-only-metrics',{...record(next.pending_action,[],['work/metrics.json']),findings:[]}));
 const current=JSON.parse(h.state.notes.at(-1).text).snapshot;
 assert.deepEqual(current.active_products.slice(0,3),before.active_products.slice(0,3),'Three valid output references stay unchanged');
 assert.equal(current.active_products[3].ref,diagnostic.products[0].current_ref);
 assert.equal(current.phase,'assessing','Re-registration still requires a separate assessment');
 assert.equal(result(await h.call('deliver-current',{...assess(repaired.pending_action,[repairRef]),coverage:[{objective_id:'rebind',status:'met',refs:[repairRef],explanation:'Verified actual current metrics'}]})).status,'done');
});
test('split-only registration derives narrow schemas and fixes canonical operation on the shared controller',async()=>{
 const h=harness({applicationPolicy:{allowed_tools:splitNames}});
 assert.deepEqual([...h.tools.keys()],splitNames);
 for(const [i,name] of splitNames.entries()){
  const schema=h.tools.get(name).parameters;
  assert.equal(schema.type,'object');assert.equal(schema.additionalProperties,false);
  assert.ok(!Object.hasOwn(schema.properties,'operation'));assert.ok(!schema.required.includes('operation'));
  assert.equal(schema.oneOf,undefined);
 }
 assert.ok(!Object.hasOwn(h.tools.get(splitNames[0]).parameters.properties,'coverage'));
 assert.deepEqual(h.tools.get(splitNames[2]).parameters.properties.checks.items.properties.status.enum,['passed','failed','not_run']);
 const invoke=(name,id,args)=>h.tools.get(name).execute(id,args);
 const strip=({operation,...args})=>args;
 const planned=result(await invoke(splitNames[0],'split-plan',strip(plan)));
 assert.match(planned.next_action,/agent_research_record/);assert.doesNotMatch(planned.next_action,/operation=/);
 assert.equal(JSON.parse(h.state.notes.at(-1).text).snapshot.phase,'executing');
 const before=h.requests.length;
 result(await invoke(splitNames[0],'split-plan',strip(plan)));assert.equal(h.requests.length,before);
 const identity=await invoke(splitNames[1],'split-plan',strip(record(planned.pending_action,[],[])));
 assert.equal(identity.details.error.code,'research_call_identity_changed');
 const ref=await h.observe();
 const recorded=result(await invoke(splitNames[1],'split-record',strip(record(planned.pending_action,[ref]))));
 assert.match(recorded.next_action,/agent_research_assess/);assert.doesNotMatch(recorded.next_action,/operation=/);
 const done=result(await invoke(splitNames[2],'split-assess',strip(assess(recorded.pending_action,[ref]))));
 assert.equal(done.status,'done');
 const checkpoint=JSON.parse(h.state.notes.at(-1).text);
 assert.equal(checkpoint.receipts.length,1,'Control calls cannot become execution receipts');
});
test('each split wrapper rejects caller operation and errors before commit with an actual-name error hook',async()=>{
 const h=harness({applicationPolicy:{allowed_tools:splitNames}});
 for(const name of splitNames){
  const failed=await h.tools.get(name).execute('invalid-'+name,{operation:'plan'});
  assert.equal(failed.details.ok,false);assert.equal(h.requests.length,0);
  assert.deepEqual(h.hooks.get('tool_result')({toolName:name,details:failed.details}),{isError:true});
  assert.match(await h.controller.continuation(),/agent_research_plan/,'An attempted invalid wrapper call keeps repair intent');
 }
 const failed=await h.tools.get(splitNames[0]).execute('extra',{...(({operation,...args})=>args)(plan),extra:true});
 assert.equal(failed.details.ok,false);assert.equal(h.requests.length,0);
 assert.match(h.hooks.get('before_agent_start')({systemPrompt:''}).systemPrompt,/agent_research_plan/);
 await assert.rejects(h.controller.beginTool({toolCallId:'control',toolName:splitNames[0]}),/control/i);
});
test('explicit grants never register an ungranted research control entrance',()=>{
 assert.deepEqual([...harness({applicationPolicy:{allowed_tools:[]}}).tools.keys()],[]);
 assert.deepEqual([...harness({applicationPolicy:{allowed_tools:['agent_research_cycle']}}).tools.keys()],['agent_research_cycle']);
});
test('bound operations keep legacy canonical identity and protected recovery and cancellation',async()=>{
 const legacy=harness(),h=harness({applicationPolicy:{allowed_tools:splitNames}});
 const args=(({operation,...value})=>value)(plan);
 result(await legacy.call('same-plan',plan));
 result(await h.tools.get(splitNames[0]).execute('same-plan',args));
 assert.deepEqual(h.requests[0],legacy.requests[0],'Public wrappers preserve the canonical operation and immutable checkpoint');
 const cancelled=harness({applicationPolicy:{allowed_tools:splitNames}}),abort=new AbortController();abort.abort();
 await assert.rejects(cancelled.tools.get(splitNames[0]).execute('cancelled',args,abort.signal));
 assert.equal(cancelled.requests.length,0);
 const unknown=harness({applicationPolicy:{allowed_tools:splitNames}});unknown.unknown();
 assert.equal((await unknown.tools.get(splitNames[0]).execute('unknown',args)).details.ok,false);
 const frozen=unknown.requests[0];
 result(await unknown.tools.get(splitNames[0]).execute('unknown',args));
 assert.deepEqual(unknown.requests[1],frozen);
 assert.equal(unknown.events.length,1);
});
