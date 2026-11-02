// Test-only bridge to the real Python context provider and native event guard.
import assert from 'node:assert/strict';
import {createInterface} from 'node:readline';
import {mkdir,readFile} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createEnterpriseGraphController} from '../../src/capstone_agent/resources/enterprise-graph-runtime.mjs';
import {createGraphContextClient} from '../../src/capstone_agent/resources/graph-context-client.mjs';
import {createGraphNodeDispatcher,configureGraphParentContext,applicationToolOptions,createIsolatedNativeTools,runSettledPrompt} from '../../src/capstone_agent/resources/general-sdk.mjs';

const lines=createInterface({input:process.stdin});
const setup=await new Promise(resolve=>lines.once('line',line=>resolve(JSON.parse(line))));
const autonomous=setup.scenario==='autonomous';
const summaryOnly=setup.scenario==='limited-summary',limitedSource=autonomous||summaryOnly;
const workEdition=limitedSource||setup.scenario==='work-valid';
const pending=new Map(),nativeHistory=[];let nextId=0,eventQueue=Promise.resolve();
lines.on('line',line=>{const reply=JSON.parse(line),request=pending.get(reply.id);pending.delete(reply.id);
  if(reply.error)request.reject(Error(reply.error));else request.resolve(reply.value);});
const rpc=(operation,value)=>new Promise((resolve,reject)=>{const id=++nextId;pending.set(id,{resolve,reject});process.stdout.write(JSON.stringify({id,operation,value})+'\n');});
const sdkRoot=resolve('.grid-agent/runtime/pi/source/packages');
const sdk=await import(pathToFileURL(join(sdkRoot,'coding-agent/dist/index.js')).href);
const ai=await import(pathToFileURL(join(sdkRoot,'ai/dist/index.js')).href);
process.chdir(setup.workspace);process.env.PI_CODING_AGENT_DIR=join(setup.workspace,'.pi');await mkdir(process.env.PI_CODING_AGENT_DIR);
const owner=setup.owner,config={researchTaskId:setup.task_id,researchAttemptId:setup.attempt_id,researchOwner:owner,model:'chain-offline',
  ...(workEdition?{deadlineAt:Date.now()+1800000}:{}),
  graphContextPath:setup.context_root,researchChannelPath:'test-only-private',researchSources:[],extensions:[],allowedSkills:[],contextFiles:[],
  settings:{compaction:{enabled:false},packages:[],extensions:[],skills:[]},applicationPolicy:{allowed_tools:['read','write','agent_research_inspect','agent_research_record','agent_research_assess']},
  researchRuntime:{graphSchema:'capstone-enterprise-graph/2',...(workEdition?{graphWorkEdition:'capstone-graph-work/1',graphWorkStartedAt:Date.now()-99000,
    graphWork:{schema:'capstone-graph-work/1',mode:'usable_draft',target_seconds:240,integration_reserve_seconds:60,child_wrapup_seconds:15}}:{}),delegation:{concurrency:2,maxTurns:8,graceTurns:1},
    graphLimits:{maxNodes:8,maxItems:128,maxText:4096,maxExecutions:32,snapshotBytes:1500000,publicBytes:200000,resultBytes:50000}}};
const model={id:config.model,name:'Offline',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',reasoning:false,
  input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
const turns=new Map(),contexts=new Map(),nativeRefs=new Map(),copiedBindings=new Map(),manifests=new Map();let parentAction,reportRef,producerRef,controller,dispatch,launches=0;
const derivedBytes='value\n3\n7\n'+(setup.scenario==='fresh-version'?'\n':'');
let releaseProducer;const producerGate=new Promise(resolve=>{releaseProducer=resolve;});
const textMessages=context=>context.messages.filter(item=>item.role==='user').flatMap(item=>typeof item.content==='string'?[item.content]:item.content.filter(block=>block.type==='text').map(block=>block.text));
const mapFrom=context=>{
  const line=textMessages(context).flatMap(text=>text.split('\n')).find(line=>line.startsWith('Exact host-selected immutable input manifests and file map'));
  return line?JSON.parse(line.slice(line.indexOf('): ')+3)):null;
};
const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
  streamSimple(_model,context,options={}){
    const contractLine=textMessages(context).flatMap(text=>text.split('\n')).find(line=>line.startsWith('Committed node contract: '));
    const contract=contractLine?JSON.parse(contractLine.slice('Committed node contract: '.length)):null;
    const id=contract?.node_id??'P',turn=turns.get(id)??0;turns.set(id,turn+1);contexts.set(id,contract);
    const results=context.messages.filter(item=>item.role==='toolResult'),last=results.at(-1);
    const observed=results.filter(item=>item.details?.native_research_source).map(item=>item.details.native_research_source.source_ref);
    nativeRefs.set(id,observed);
    let call;
    if(contract){
      const observationOnly=id==='O';
      assert.deepEqual(contract.outputs,[{slot:'file',kind:observationOnly?'observation':'artifact',description:id==='A'?'Reusable derived table':observationOnly?'Contract observation':'Independent retained output'},
        ...(autonomous&&id==='A'?[{slot:'optional',kind:'artifact',description:'Unfinished optional rendering'}]:[])]);
      if(workEdition){assert.equal(contract.work_envelope.target_seconds,240);assert.ok(contract.work_envelope.finish_by_ms-Date.now()<82000);}
      assert.deepEqual(contract.checks,['Inspect exact saved bytes']);assert.deepEqual(contract.binding.source_versions,[]);
      assert.equal(contract.schema,'capstone-node-contract/1');
      const mapped=mapFrom(context),reading=id==='C';
      if(id==='A'&&setup.scenario==='fresh-version'&&turn===4){
        assert.match(textMessages(context).find(text=>text.startsWith('Your node proposal was definitively rejected')),/output_support/);
        call={name:'write',arguments:{path:'derived.csv',content:derivedBytes}};
      }else if(id==='A'&&setup.scenario==='fresh-version'&&turn===5){
        const manifest=manifests.get(id),ref=last.content.find(item=>item.type==='text'&&item.text.startsWith('Host observation reference: ')).text.slice('Host observation reference: '.length);
        manifest.graph_proposal.checks[0].refs=[ref];manifest.graph_proposal.outputs[0].observation_refs=[ref];
        call={name:'write',arguments:{path:'.capstone-products.json',content:JSON.stringify(manifest)}};
      }else if(id==='A'&&['feedback','repeated'].includes(setup.scenario)&&turn===4){
        const feedback=textMessages(context).find(text=>text.startsWith('Your node proposal was definitively rejected'));
        assert.match(feedback,/check_support_missing/);assert.match(feedback,/Inspect exact saved bytes/);
        // A real Provider sees tool content, not the SDK's private details.
        const support=results.flatMap(item=>item.content).filter(item=>item.type==='text'&&item.text.startsWith('Host observation reference: '))
          .map(item=>item.text.slice('Host observation reference: '.length))[1];
        assert.ok(support);const manifest=manifests.get(id);manifest.graph_proposal.checks[0].refs=setup.scenario==='repeated'?[]:[support];
        manifest.graph_proposal.checks[0].explanation='Changed prose does not create check support';
        call={name:'write',arguments:{path:'.capstone-products.json',content:JSON.stringify(manifest)}};
      }else if(turn===0){
        const line=textMessages(context).flatMap(text=>text.split('\n')).find(line=>line.startsWith('Private read-only node contract file: '));
        const path=JSON.parse(line.match(/^Private read-only node contract file: ("(?:\\.|[^"\\])*")/)[1]);
        call={name:'read',arguments:{path}};
      }else if(reading&&turn===1){
        copiedBindings.set(id,JSON.parse(last.content[0].text).binding);
        assert.deepEqual(contract.binding.consumed_results,[producerRef]);assert.deepEqual(mapped.handles.filter(item=>item.kind==='product').map(item=>item.result_ref),[producerRef]);
        call={name:'read',arguments:{path:mapped.handles.find(item=>item.kind==='product').path}};
      }else if(!observationOnly&&turn===(reading?2:1)){
        if(!reading)copiedBindings.set(id,JSON.parse(last.content[0].text).binding);
        if(reading)assert.equal(last.content[0].text,derivedBytes);
        call={name:'write',arguments:{path:id==='A'?'derived.csv':'side.txt',content:id==='A'?'value\n3\n7\n':'Consumed exact derived version\n'}};
      }else if(turn===(observationOnly?1:reading?3:2)){
        if(observationOnly)copiedBindings.set(id,JSON.parse(last.content[0].text).binding);
        const filename=id==='A'?'derived.csv':'side.txt',support=observed.at(-1);
        const manifest={schema:'capstone-workspace-products/1',products:observationOnly?[]:[{path:filename,role:'support'}],graph_proposal:{
          schema:'capstone-node-proposal/1',binding:copiedBindings.get(id),
          outputs:[{slot:'file',product_paths:observationOnly?[]:[filename],observation_refs:[support],summary:observationOnly?'Observed exact node contract':'Exact saved output',scope:'Declared node contract'}],
          checks:[{description:contract.checks[0],status:autonomous&&id==='A'?'not_run':'passed',refs:id==='A'&&['feedback','repeated'].includes(setup.scenario)?[]:[support],explanation:'Actual saved output observation'}],
          limitations:autonomous&&id==='A'?['Optional rendering was not completed; retained numeric table is usable']:[]}};
        manifests.set(id,manifest);call={name:'write',arguments:{path:'.capstone-products.json',content:JSON.stringify(manifest)}};
      }
    }else{
      const mapped=mapFrom(context);
      if(turn===0){assert.equal(mapped.manifests[0].result_ref,producerRef);call={name:'read',arguments:{path:mapped.handles.find(item=>item.kind==='product').path}};}
      if(turn===1){assert.equal(last.content[0].text,derivedBytes);call={name:'write',arguments:{path:'report.md',content:'# Report\n\nRetained values: 3, 7.\n'}};}
      if(turn===2)call={name:'agent_research_inspect',arguments:{action_id:parentAction.id,products:[{path:'missing.md',role:'primary'}]}};
      if(turn===3){assert.equal(last.details.error.category,'rejected');assert.equal(last.details.error.recovery,'correct_selection');assert.match(last.details.error.request_id,/^ctx-/);
        call={name:'agent_research_inspect',arguments:{action_id:parentAction.id,products:[{path:'report.md',role:'primary'}]}};}
      if(turn===4){assert.equal(last.details.ok,true,JSON.stringify(last));reportRef=last.details.result.products[0].ref;
        call={name:'agent_research_record',arguments:{action_id:parentAction.id,outcome:'completed',outputs:[{slot:'report',artifact_refs:[reportRef],observation_refs:observed,
          summary:'Report reads exact retained bytes',scope:'Selected derived version'}],limitations:[]}};}
      if(setup.scenario==='parent-record'&&turn===5){
        assert.equal(last.details.ok,false);assert.match(last.details.error.message,/all declared output slots/);
        call={name:'agent_research_inspect',arguments:{action_id:parentAction.id,products:[{path:'report.md',role:'primary'}]}};
      }
      if(setup.scenario==='parent-record'&&turn===6){
        assert.equal(last.details.ok,true,JSON.stringify(last));assert.equal(last.details.result.products[0].ref,reportRef);
        call={name:'agent_research_record',arguments:{action_id:parentAction.id,outcome:'completed',outputs:[
          {slot:'report',artifact_refs:[reportRef],observation_refs:observed,summary:'Report reads exact retained bytes',scope:'Selected derived version'},
          {slot:'support',artifact_refs:[],observation_refs:observed,summary:'Actual observed read and save',scope:'Same parent execution'}],limitations:[]}};
      }
      if(turn===(setup.scenario==='parent-record'?7:5)){assert.equal(last.details.ok,true,JSON.stringify(last));const assess=last.details.result.graph.actions.find(item=>item.kind==='assess'&&item.step_id==='P');
        call={name:'agent_research_assess',arguments:{action_id:assess.id,outcome:'success',checks:[{description:'Inspect report output',status:'passed',refs:observed,explanation:'Actual selected read and saved report'}],summary:'Parent accepted exact retained report'}};}
      if(turn===6)assert.equal(last.details.ok,true,JSON.stringify(last));
    }
    const message={role:'assistant',content:call?[{type:'toolCall',id:id+'-call-'+turn,...call}]:[{type:'text',text:'Assigned work complete; retained exact associations.'}],stopReason:call?'toolUse':'stop',
      api:model.api,provider:model.provider,model:model.id,timestamp:0,usage:{input:2,output:3,cacheRead:0,cacheWrite:0,totalTokens:5,cost:{total:0}}};
    const stream=ai.createAssistantMessageEventStream();
    let finished=false;
    const complete=()=>{if(finished)return;finished=true;stream.push({type:'done',reason:message.stopReason,message});stream.end();};
    if(id==='A'&&turn===0){
      options.signal?.addEventListener('abort',()=>{if(finished)return;finished=true;stream.push({type:'error',reason:'aborted',error:{...message,content:[],stopReason:'aborted'}});stream.end();},{once:true});
      producerGate.then(complete);
    }else complete();return stream;
  }};
const emit=event=>{nativeHistory.push([event.child_id,event.type,event.activity,event.tool_name]);eventQueue=eventQueue.then(()=>rpc('native',event));};
const context=createGraphContextClient(config,{emit:async frame=>{await eventQueue;await rpc('context',frame);}});
let view={research_revision:0,state:null};
const checkpointFor=action=>{
  const notes=view.state.notes.map(note=>({note,saved:JSON.parse(note.text)})).filter(item=>item.saved.snapshot.actions.some(item=>item.id===action.id));
  const latest=notes.sort((a,b)=>b.saved.committed_revision-a.saved.committed_revision)[0];
  return {ref:latest.note.note_id,revision:latest.saved.committed_revision};
};
let loseRecord=true,injectedVersionDefect=false;
const ports={config,readResearch:async()=>structuredClone(view),
  commitResearch:async(id,request)=>{
    const reply=await rpc('commit',{id,request});view=reply.view;
    if(loseRecord&&JSON.parse(request.changes.notes.at(-1).text).command_id==='record-A'){loseRecord=false;return {details:{ok:false}};}
    return reply.ack;
  },onProgress:async event=>{await eventQueue;await rpc('progress',event);},
  resolveInputs:async(action,control)=>{const result=await context.resolve({action,checkpoint:checkpointFor(action),selection:{result_refs:action.input_bindings.map(item=>item.result_ref),product_refs:[]}},control);
    return {manifests:result.manifests,handles:result.handles};},
  inspectProducts:async({action,products,productRefs},control)=>productRefs?{ready:true,...await context.resolve({action,checkpoint:checkpointFor(action),selection:{result_refs:[],product_refs:productRefs}},control)}:
    context.freeze({action,checkpoint:checkpointFor(action),selection:{products}},control),
  dispatchNode:async(request,control)=>{
    launches++;
    if(setup.scenario==='fresh-version'&&request.node.id==='A'){
      const validate=control.validateProposal;
      control={...control,validateProposal:candidate=>{
        if(!candidate.metadata&&!injectedVersionDefect){
          injectedVersionDefect=true;const wrong=structuredClone(candidate);wrong.handoff.outputs[0].artifact_refs=['unadmitted-product'];
          return validate(wrong); // Real validator rejects only after a real successful freeze.
        }
        return validate(candidate);
      }};
    }
    return dispatch(request,control);
  }};
controller=createEnterpriseGraphController(ports);dispatch=createGraphNodeDispatcher(config,sdk,runtime,{skills:[],contextClient:context,emit});
const node=(id,extra={})=>({id,purpose:'Bounded '+id,questions:['What was saved?'],checks:['Inspect exact saved bytes'],depends_on:[],expected_outputs:['Exact saved file'],
  mode:'execute',execution:'delegated',instruction:'Complete only this declared contract',source_refs:[],outputs:[{slot:'file',kind:'artifact',description:id==='A'?'Reusable derived table':'Independent retained output'}],inputs:[],...extra});
const definitions=[node('A',autonomous?{outputs:[{slot:'file',kind:'artifact',description:'Reusable derived table'},{slot:'optional',kind:'artifact',description:'Unfinished optional rendering'}]}:{}),
  node('C',{depends_on:['A'],inputs:[{name:'derived',from:{step_id:'A',slot:'file'}}]}),
  node('O',{depends_on:['A'],outputs:[{slot:'file',kind:'observation',description:'Contract observation'}]}),node('P',{execution:'parent',mode:'synthesis',depends_on:['A'],
    checks:['Inspect report output'],outputs:[{slot:'report',kind:'artifact',description:'Report from retained data'},
      ...(setup.scenario==='parent-record'?[{slot:'support',kind:'observation',description:'Observed report inputs and saved output'}]:[])],inputs:[{name:'derived',from:{step_id:'A',slot:'file'}}]})];
const planned=await controller.execute('plan','plan',{goal:'Retain and consume exact shared results',output_mode:'files',source_refs:[],nodes:definitions});
assert.equal(planned.details.ok,true);
if(setup.cancel){
  for(let i=0;i<100&&!turns.has('A');i++)await new Promise(resolve=>setTimeout(resolve,2));
  assert.equal(turns.get('A'),1);await controller.close({reason:'Explicit test cancellation'});await eventQueue;
  const stopped=await controller.readState();assert.equal(stopped.graph.nodes.find(item=>item.id==='A').settled_status,'cancelled');
  controller=createEnterpriseGraphController({...ports,dispatchNode:()=>assert.fail('Cancelled work must not relaunch on restore')});
  await controller.readState();
  const delivery=await controller.finish('finish-cancel',{outcome:'failure',delivery_result_refs:[],delivery_product_refs:[],limitations:['Explicit cancellation retained actual status'],summary:'No delivery claimed'});
  assert.equal(delivery.details.ok,true);await controller.close();await eventQueue;
  await rpc('done',{cancelled:true,launches,delivery:delivery.details.result});lines.close();process.exit(0);
}
let yieldResponses=0;
const yieldingRuntime={...runtime,streamSimple(){
  yieldResponses++;const message={role:'assistant',content:[{type:'text',text:'The declared producer is running. Yield until a proposal is ready.'}],stopReason:'stop',
    api:model.api,provider:model.provider,model:model.id,timestamp:0,usage:{input:2,output:3,totalTokens:5,cost:{total:0}}};
  const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:'stop',message});stream.end();return stream;
}};
const yielding=await sdk.createAgentSession({cwd:setup.workspace,agentDir:process.env.PI_CODING_AGENT_DIR,modelRuntime:yieldingRuntime,model,
  settingsManager:sdk.SettingsManager.inMemory(config.settings),sessionManager:sdk.SessionManager.inMemory(),tools:[]});
try{
  await runSettledPrompt(yielding.session,{kind:'text',text:'Let the declared producer finish; no parent work is ready.'},null,()=>{},async()=>{
    const wake=controller.continuationState();releaseProducer();const packet=await wake;
    assert.ok(JSON.parse(packet.prompt).pending_proposals.some(item=>item.step_id==='A'));return null;
  });
}finally{yielding.session.dispose();}
assert.equal(yieldResponses,1);
async function settled(id){let last;for(let i=0;i<1000;i++){last=await controller.readState();if(last.graph.nodes.find(item=>item.id===id).phase==='executed')return last;
  await new Promise(resolve=>setTimeout(resolve,2));}throw Error('Fixture execution failed to settle '+id+' '+JSON.stringify({nodes:last.graph.nodes.map(item=>({id:item.id,phase:item.phase})),
    update_pending:last.update_pending,settlement_pending:last.settlement_pending,proposals:last.pending_proposals.map(item=>({step_id:item.step_id,status:item.status})),turns:Object.fromEntries(turns),history:nativeHistory.filter(item=>item[0]==='C').slice(-9)}));}
async function accept(id){
  let state=await settled(id),proposal=state.pending_proposals.find(item=>item.step_id===id).proposal;
  const partial=autonomous&&id==='A';
  if(partial){assert.equal(proposal.status,'incomplete');assert.equal(proposal.proposal_ref,undefined);assert.deepEqual(proposal.missing_slots,['optional']);}
  else
  assert.equal(proposal.status,'validated',JSON.stringify({proposal,status:state.pending_proposals.find(item=>item.step_id===id).status,
    output:state.pending_proposals.find(item=>item.step_id===id).output,turns:Object.fromEntries(turns)}));const action=state.graph.nodes.find(item=>item.id===id).execute_action_id;
  const args={action_id:action,...(partial?{outputs:proposal.outputs}:{proposal_ref:proposal.proposal_ref}),outcome:partial?'limited':'completed',limitations:partial?proposal.limitations:[]};
  let record=await controller.execute('record','record-'+id,args);
  if(id==='A'){
    assert.equal(record.details.ok,false);assert.equal(record.details.error.category,'unknown');
    record=await controller.execute('record','record-'+id,args);
  }
  assert.equal(record.details.ok,true,JSON.stringify(record));state=await controller.readState();
  if(id==='A')producerRef=state.graph.nodes.find(item=>item.id==='A').output_bindings[0].result_ref;
  const assess=state.graph.nodes.find(item=>item.id===id).assess_action_id;
  const summaryLimited=summaryOnly&&id==='A';
  assert.equal((await controller.execute('assess','assess-'+id,{action_id:assess,...(summaryLimited?{checks:[]}:partial?{checks:proposal.checks}:{proposal_ref:proposal.proposal_ref}),
    outcome:partial||summaryLimited?'limited':'success',summary:summaryLimited?'LIMIT_REASON_ONLY_IN_SUMMARY':'Parent accepted producer check claims with actual support'})).details.ok,true);
  return (await controller.readState()).graph.nodes.find(item=>item.id===id).output_bindings[0].result_ref;
}
if(setup.scenario==='repeated'){
  const state=await settled('A'),pending=state.pending_proposals.find(item=>item.step_id==='A');
  assert.equal(pending.status,'completed');assert.equal(pending.proposal.status,'rejected');assert.equal(turns.get('A'),6);
  await controller.close();await eventQueue;
  controller=createEnterpriseGraphController({...ports,dispatchNode:()=>assert.fail('Rejected settled work must not relaunch')});
  const restored=await controller.readState();assert.equal(restored.pending_proposals[0].proposal.diagnostic.code,'check_support_missing');
  const failed=await controller.finish('finish-rejected',{outcome:'failure',delivery_result_refs:[],delivery_product_refs:[],limitations:['Producer check support was not supplied'],summary:'No typed proposal was accepted'});
  assert.equal(failed.details.ok,true);await controller.close();await eventQueue;
  await rpc('done',{repeated:true,launches,turns:Object.fromEntries(turns),delivery:failed.details.result});lines.close();process.exit(0);
}
producerRef=await accept('A');
if(limitedSource){
  const state=await controller.readState(),producer=state.graph.nodes.find(item=>item.id==='A');
  assert.equal(producer.phase,'limited');assert.equal(state.graph.nodes.find(item=>item.id==='C').phase,'pending');
  const revised=structuredClone(definitions);
  for(const node of revised.filter(item=>item.id!=='A'))node.inputs=[{name:'derived',result_ref:producerRef,
    accept_limited:{assessment_ref:producer.assessment_ref,rationale:'Use the retained numeric table while preserving the omitted optional rendering'}}];
  const reply=await controller.execute('revise','accept-limited',{nodes:revised,reason:'Explicitly accept the exact assessed limited table for these consumers',rerun:[]});
  assert.equal(reply.details.ok,true,JSON.stringify(reply));
}
assert.equal((await controller.execute('start','start-P',{step_id:'P',kind:'execute'})).details.ok,true);
parentAction=(await controller.readParentInputs()).action;
await accept('C'); // A real sibling checkpoint advances while the parent remains executing.
await accept('O');
const settingsManager=sdk.SettingsManager.inMemory(config.settings);let guard;
const loader=new sdk.DefaultResourceLoader({cwd:setup.workspace,agentDir:process.env.PI_CODING_AGENT_DIR,settingsManager,noExtensions:true,noSkills:true,
  noPromptTemplates:true,noThemes:true,noContextFiles:true,agentsFilesOverride:()=>({agentsFiles:[]}),extensionFactories:[pi=>{
    guard=configureGraphParentContext(pi,config,controller);controller.register(pi);
    pi.on('tool_result',event=>event.details?.ok===false?{isError:true}:undefined);
  }]});await loader.reload();
const tools=applicationToolOptions(config,createIsolatedNativeTools(sdk,setup.workspace),()=>controller);
const {session}=await sdk.createAgentSession({cwd:setup.workspace,agentDir:process.env.PI_CODING_AGENT_DIR,settingsManager,resourceLoader:loader,
  modelRuntime:runtime,model,...tools,sessionManager:sdk.SessionManager.inMemory()});
const originalWrite=process.stdout.write;
// Parent native wrappers emit the same JSON frames as the deployed SDK.
process.stdout.write=chunk=>{const value=JSON.parse(chunk);if(value.id!==undefined)return originalWrite.call(process.stdout,chunk);emit(value);return true;};
try{
  await session.bindExtensions({onError:()=>{}});session.setActiveToolsByName(config.applicationPolicy.allowed_tools);
  await runSettledPrompt(session,{kind:'text',text:'Compose only the declared report from its exact granted version.'},null,()=>{},undefined,{failure:()=>guard.failure()});
}finally{session.dispose();process.stdout.write=originalWrite;}
await eventQueue;
const beforeRestore=launches;await controller.close();
controller=createEnterpriseGraphController({...ports,dispatchNode:()=>assert.fail('Restore must not relaunch accepted work')});
const restored=await controller.readState();assert.equal(launches,beforeRestore);
const report=restored.graph.nodes.find(item=>item.id==='P').output_bindings[0].result_ref;
const delivery=await controller.finish('finish',{outcome:limitedSource?'limited':'success',delivery_result_refs:[report],delivery_product_refs:[reportRef],limitations:limitedSource?['Useful draft retains the producer limitation']:[],summary:'Delivered exact retained report'});
assert.equal(delivery.details.ok,true,JSON.stringify(delivery));
assert.equal(await readFile(join(setup.workspace,'report.md'),'utf8'),'# Report\n\nRetained values: 3, 7.\n');
await controller.close();await eventQueue;
await rpc('done',{launches,yield_responses:yieldResponses,turns:Object.fromEntries(turns),producer_ref:producerRef,report_ref:report,delivery:delivery.details.result,
  consumer_input:contexts.get('C').binding.consumed_results,private_map_in_history:session.messages.some(item=>item.customType==='capstone-graph-parent-inputs')});
lines.close();
