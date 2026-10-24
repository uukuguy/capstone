import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm,realpath,cp,symlink,readFile,stat,readdir} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';
import * as sdkHost from '../../src/capstone_agent/resources/general-sdk.mjs';
import {createEnterpriseGraphController} from '../../src/capstone_agent/resources/enterprise-graph-runtime.mjs';
import {createGraphContextClient} from '../../src/capstone_agent/resources/graph-context-client.mjs';
import {createTaskNodeReturn} from '../../src/capstone_agent/resources/task-node-return.mjs';

test('SDK selects the graph adapter only for its explicit schema',()=>{
  assert.equal(sdkHost.usesEnterpriseGraph({researchRuntime:{graphSchema:'capstone-enterprise-graph/2'}}),true);
  assert.equal(sdkHost.usesEnterpriseGraph({researchRuntime:{enabled:true}}),false);
  assert.equal(sdkHost.usesEnterpriseGraph({researchRuntime:{graphSchema:'capstone-enterprise-cycle/1'}}),false);
});
test('parent binding keeps the exact token checkpoint across sibling commits',async()=>{
  const frames=[],token={toolCallId:'call',toolName:'read',action:{id:'action-A',step_id:'A',owner:{thread_id:'T'},attempt_id:'attempt'},checkpoint:{ref:'old',revision:1}};
  let saved;
  const config={researchChannelPath:'private',researchTaskId:'task',researchRuntime:{graphSchema:'capstone-enterprise-graph/2'},applicationPolicy:{allowed_tools:['read']}};
  const original=process.stdout.write;process.stdout.write=chunk=>{frames.push(JSON.parse(chunk));return true;};
  try{
    const controller={beginTool:async()=>token,completeTool:async(actual,result)=>{saved={actual,result};return result;}};
    const tool=sdkHost.applicationToolOptions(config,[{name:'read',execute:async()=>({content:[{type:'text',text:'real observation'}]})}],()=>controller).customTools[0];
    await tool.execute('call',{});
    assert.equal(frames[0].type,'enterprise_graph_tool_binding');
    assert.equal(frames[0].action_id,'action-A');assert.deepEqual(frames[0].checkpoint,{ref:'old',revision:1});
    assert.equal(saved.actual,token);assert.match(saved.result.details.native_research_source.source_ref,/^native-observation:task:/);
  }finally{process.stdout.write=original;}
});

function fakeSdk(observe,{block=false,saveBeforeBlock=false}={}){
  return {
    SettingsManager:{inMemory:()=>({})},SessionManager:{inMemory:()=>({})},
    DefaultResourceLoader:class{constructor(options){observe.loader=options;}async reload(){}getExtensions(){return {errors:[]};}getSkills(){return {skills:[],diagnostics:[]};}},
    createCodingTools:cwd=>[{name:'write',async execute(id,args){await writeFile(join(cwd,args.path),args.text);return {content:[{type:'text',text:'saved actual bytes'}]};}}],
    async createAgentSession(options){
      observe.options=options;let aborted;
      const listeners=new Set();const emit=event=>listeners.forEach(fn=>fn(event));
      const session={messages:[],subscribe(fn){listeners.add(fn);return()=>listeners.delete(fn);},async bindExtensions(){},setActiveToolsByName(names){observe.activeTools=names;},
        extensionRunner:{async emit(){}},dispose(){observe.disposed=true;observe.closes=(observe.closes??0)+1;},steer(){observe.steered=true;},async abort(){observe.aborted=true;aborted?.();},async prompt(prompt){
          observe.prompt=prompt;observe.prompts=(observe.prompts??0)+1;emit({type:'turn_start'});
          await observe.beforePrompt?.(prompt);if(observe.aborted)return;
          if(block){
            if(saveBeforeBlock){await writeFile(join(options.cwd,'report.txt'),'saved before cancellation');observe.saved=true;}
            await new Promise(resolve=>aborted=resolve);return;
          }
          const observed=observe.manifestOnlyCorrection&&observe.prompts>1?observe.lastObserved:
            await options.customTools[0].execute('native-call'+(observe.prompts===1?'':observe.prompts),{path:'report.txt',text:observe.reportText?.(observe.prompts)??'actual report'});
          observe.lastObserved=observed;
          await writeFile(join(options.cwd,'.capstone-products.json'),observe.manifestText??JSON.stringify(observe.returnValue?observe.returnValue(prompt,observed):{schema:'capstone-workspace-products/1',products:[{path:'report.txt',role:'primary'}],
            ...(observe.propose?{graph_proposal:observe.propose(prompt,observed)}:{})}));
          const message={role:'assistant',content:[{type:'text',text:'Observed result proposal'}],stopReason:'stop',usage:{input:2,output:3,totalTokens:5,cost:{total:0.1}}};
          session.messages.push(message);emit({type:'message_end',message});emit({type:'turn_end'});
        }};return {session};
    }
  };
}
const node={id:'A',title:'Exact node',instruction:'EXACT INSTRUCTION',questions:['EXACT QUESTION'],expected_outputs:['EXACT OUTPUT']};
const action={id:'action-A',step_id:'A',owner:{thread_id:'T'},attempt_id:'attempt',input_bindings:[],source_refs:[],source_versions:[]};
const checkpoint={ref:'checkpoint-A',revision:1};
for(const admission of ['available','partial','unconfirmed'])test('task completion records without model resubmission: '+admission,async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-structured-return-'))),previous=process.cwd();process.chdir(dir);
  const seen={},receipts=[],frames=[],config={researchTaskId:'task',model:'fake',extensions:[],allowedSkills:[],settings:{},
    applicationPolicy:{allowed_tools:['write']},researchRuntime:{lightweightTaskNodes:true}};
  const declared={...node,purpose:'State a useful finding',outputs:[{slot:'file',kind:'artifact',description:'Saved report'}],checks:['Independent review']};
  const adapter=createTaskNodeReturn({...action,definition_ref:'definition-A',execution_revision:1},declared,{manifests:[],handles:[]});
  let child,sealed;
  try{
    await writeFile(join(dir,'report.txt'),'actual saved bytes');
    child=await sdkHost.createManagedChildSession(config,fakeSdk(seen),{getModel:()=>({id:'fake'})},{cwd:dir,toolNames:['write'],researchExecution:true,
      graphBinding:{action,checkpoint,emit:event=>{
        if(event.type==='enterprise_graph_child_tool'&&event.activity==='end'&&!event.is_error)assert.ok(sealed,'Files must be retained before the return observation is published');
        frames.push(event);
      },receipts,taskReturn:adapter,freezeReturn:async({products})=>{sealed=products;if(admission==='unconfirmed')throw new Error('Admission unavailable');return admission==='partial'?{unavailable:[{path:'missing.py',code:'source_missing'}]}:{};}}});
    const tool=seen.options.customTools.find(item=>item.name==='agent_task_return');assert.ok(tool);
    assert.ok(seen.activeTools.includes('agent_task_return'));
    const summary='保留 "引号" 与换行\nUseful result, with a stated gap.';
    const returned=await tool.execute('submit',{summary,outputs:[{slot:'file',files:[{path:'report.txt',role:'primary'}]}],limitations:['Review not performed']});
    const saved=JSON.parse(await readFile(join(dir,'.capstone-products.json'),'utf8')),normalized=adapter.normalize(saved);
    assert.equal(returned.details.task_return_saved,true);
    assert.equal(returned.isError,undefined);
    if(admission==='unconfirmed')assert.equal(returned.details.product_admission.status,'unconfirmed');
    if(admission!=='available')assert.ok(returned.details.unavailable_products.length);
    assert.equal(saved.outputs[0].summary,summary);
    assert.deepEqual(normalized.products,[{path:'report.txt',role:'primary'}]);
    assert.deepEqual(sealed,[{path:'report.txt',role:'primary'}]);
    assert.deepEqual(normalized.proposal.outputs[0].observation_refs,[receipts[0].ref]);
    assert.equal(normalized.proposal.checks[0].status,'not_run');
    assert.equal(frames.filter(event=>event.type==='enterprise_graph_child_tool'&&event.activity==='end').length,1);
    assert.deepEqual((await readdir(dir)).filter(name=>name.endsWith('.tmp')),[]);
  }finally{await child?.close();process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});
test('lightweight node capacity failure retains a diagnostic without aborting the next node',async()=>{
  const {checkCapacity,runtimeLimits}=await import('../../src/capstone_agent/resources/runtime-limits.mjs');
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-capacity-'))),previous=process.cwd();process.chdir(dir);
  const seen={beforePrompt(){checkCapacity(runtimeLimits({tool_observation_bytes:1},{mode:'debug'}),
    'tool_observation_bytes',2,'bytes','test_node');}};
  const config={researchTaskId:'task',model:'fake',extensions:[],allowedSkills:[],settings:{},contextFiles:[],runtimeLimitMode:'debug',
    applicationPolicy:{allowed_tools:['write']},researchRuntime:{lightweightTaskNodes:true,delegation:{maxTurns:4,graceTurns:1}}};
  try{
    const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk(seen),{getModel:()=>({id:'fake'}),streamSimple(){}},
      {skills:[],emit:()=>{},contextClient:{freeze:async()=>({products:[]})}});
    const result=await dispatch({action,node,inputs:{manifests:[],handles:[]},checkpoint});
    assert.equal(result.status,'failed');
    assert.equal(result.capacity.dimension,'tool_observation_bytes');
    assert.match(result.output,/capacity/i);
    // The failed session is closed; a later independent task must remain runnable.
    delete seen.aborted;
    delete seen.beforePrompt;
    const next=await dispatch({action:{...action,id:'action-B'},node,inputs:{manifests:[],handles:[]},checkpoint});
    assert.equal(next.status,'completed');
  }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});
test('lightweight dispatcher admits a compact return and publishes only its selected product',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-light-'))),previous=process.cwd();process.chdir(dir);
  const selected={...action,definition_ref:'definition-A',execution_revision:1},declared={...node,
    purpose:'Answer one question',checks:['Inspect saved bytes'],outputs:[{slot:'file',kind:'artifact',description:'Saved answer'}]};
  const seen={returnValue(prompt,result){
    assert.doesNotMatch(prompt,/COPY_THE_EXACT|product_manifest_template|source_versions/);
    assert.match(result.content.at(-1).text,/Task observation: o1/);
    return {schema:'capstone-task-return/1',outputs:[{slot:'file',summary:'Saved answer',scope:'Actual source',observations:[result.details.native_research_source.source_ref],files:[{path:'report.txt',role:'primary'}]}],
      checks:[{check:1,status:'passed',observations:['o1'],explanation:'Saved bytes observed'}],limitations:[]};
  }};
  seen.beforePrompt=async()=>{await writeFile(join(seen.options.cwd,'scratch.py'),'incidental source');};
  const config={researchTaskId:'task',model:'fake',extensions:[],allowedSkills:[],settings:{},contextFiles:[],applicationPolicy:{allowed_tools:['write']},
    researchRuntime:{lightweightTaskNodes:true,delegation:{maxTurns:4,graceTurns:1}}};
  let selection,validated;
  try{
    const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk(seen),{getModel:()=>({id:'fake'})},{skills:[],emit:()=>{},contextClient:{freeze:async request=>{
      selection=request.selection.products;return {products:[{ref:'product-file'}],selections:[{path:'report.txt',ref:'product-file'}]};
    }}});
    const result=await dispatch({action:selected,node:declared,inputs:{manifests:[],handles:[]},checkpoint,contract_schema:'capstone-node-contract/1'},
      {validateProposal:candidate=>{validated=candidate;}});
    assert.equal(result.status,'completed');assert.equal(result.handoff_error,undefined);
    assert.deepEqual(selection,[{path:'report.txt',role:'primary'}]);
    assert.equal(validated.handoff.binding.action_id,selected.id);
    assert.deepEqual(result.handoff.outputs[0].artifact_refs,['product-file']);
    assert.equal(result.handoff.checks[0].description,'Inspect saved bytes');
    assert.match(result.handoff.checks[0].refs[0],/^native-observation:task:/);
    assert.equal(seen.prompts,1);
  }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});
test('a restored lightweight synthesis cannot dispatch with ungranted sources',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-ungranted-source-'))),previous=process.cwd();process.chdir(dir);
  const seen={};
  const config={researchTaskId:'task',model:'fake',extensions:[],allowedSkills:[],settings:{},contextFiles:[],applicationPolicy:{allowed_tools:['write']},
    researchSources:[],deliveryReviewSources:[{source_ref:'raw',file_name:'raw.csv',origin:'original_input',path:'/original/raw.csv'}],
    researchRuntime:{lightweightTaskNodes:true,delegation:{maxTurns:4,graceTurns:1}}};
  const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk(seen),{getModel:()=>({id:'fake'})},{skills:[],emit:()=>{},contextClient:{}});
  try{
    await assert.rejects(dispatch({action:{...action,definition_ref:'definition-A',execution_revision:1,source_refs:['raw']},
      node:{...node,mode:'synthesis',checks:[],outputs:[]},inputs:{manifests:[],handles:[]},checkpoint,contract_schema:'capstone-node-contract/1'}),/source manifest is unavailable/i);
    assert.equal(seen.options,undefined);
  }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});
test('lightweight synthesis receives its distinct role and exact granted product identity',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-synthesis-role-'))),previous=process.cwd();process.chdir(dir);
  const selected={...action,definition_ref:'definition-A',execution_revision:1,source_refs:['prior']},declared={...node,mode:'synthesis',checks:[],
    outputs:[{slot:'file',kind:'artifact',description:'Composed output'}]};
  const seen={beforePrompt(prompt){assert.match(seen.loader.systemPromptOverride(),/You synthesize retained/);
    assert.match(prompt,/"mode":"synthesis"/);assert.match(prompt,/"source_ref":"prior"/);assert.match(prompt,/"origin":"previous_product"/);},
    returnValue:()=>({schema:'capstone-task-return/1',outputs:[{slot:'file',summary:'Composed retained facts',scope:'Actual inputs',
      observations:[],files:[{path:'report.txt',role:'primary'}]}],checks:[],limitations:[]})};
  const config={researchTaskId:'task',model:'fake',extensions:[],allowedSkills:[],settings:{},contextFiles:[],applicationPolicy:{allowed_tools:['write']},
    researchSources:['prior'],deliveryReviewSources:[{source_ref:'prior',file_name:'prefix-cached.csv',origin:'previous_product',path:join(dir,'cached.csv'),size_bytes:12}],
    researchRuntime:{lightweightTaskNodes:true,delegation:{maxTurns:4,graceTurns:1}}};
  try{
    const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk(seen),{getModel:()=>({id:'fake'})},{skills:[],emit:()=>{},
      contextClient:{freeze:async()=>({products:[{ref:'saved-report'}],selections:[{path:'report.txt',ref:'saved-report'}]})}});
    const result=await dispatch({action:selected,node:declared,inputs:{manifests:[],handles:[]},checkpoint,contract_schema:'capstone-node-contract/1'},
      {validateProposal:()=>{}});
    assert.equal(result.status,'completed');assert.equal(result.handoff_error,undefined);assert.equal(seen.prompts,1);
  }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});
test('lightweight return preserves an imperfect finding without another model or source call',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-alias-repair-'))),previous=process.cwd();process.chdir(dir);
  const selected={...action,definition_ref:'definition-A',execution_revision:1},declared={...node,
    checks:['Inspect saved output'],outputs:[{slot:'file',kind:'artifact',description:'Saved output'}]};
  const seen={manifestOnlyCorrection:true,returnValue(){return {schema:'capstone-task-return/1',
    outputs:[{slot:'file',summary:'Preserve the observed findings',scope:'Selected source',
      observations:[seen.prompts===1?'o99':'o1'],files:[{path:'report.txt',role:'primary'}]}],
    checks:[{check:1,status:'passed',observations:['o1'],explanation:'Actual saved bytes'}],limitations:[]};}};
  seen.beforePrompt=async prompt=>{if(seen.prompts===2){
    assert.match(prompt,/Patch only/);assert.doesNotMatch(prompt,/Rewrite/);
    assert.match(prompt,/outputs\[0\]\.observations\[0\]/);
    assert.match(prompt,/"invalid_alias":"o99"/);assert.match(prompt,/"available_observations":\{"local":1,"inherited":0\}/);
  }};
  const config={researchTaskId:'task',model:'fake',extensions:[],allowedSkills:[],settings:{},contextFiles:[],
    applicationPolicy:{allowed_tools:['write']},researchRuntime:{lightweightTaskNodes:true,delegation:{maxTurns:4,graceTurns:1}}};
  try{
    const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk(seen),{getModel:()=>({id:'fake'})},{skills:[],emit:()=>{},
      contextClient:{freeze:async()=>({products:[{ref:'saved-file'}],selections:[{path:'report.txt',ref:'saved-file'}]})}});
    const result=await dispatch({action:selected,node:declared,inputs:{manifests:[],handles:[]},checkpoint,
      contract_schema:'capstone-node-contract/1'},{validateProposal:()=>{}});
    assert.equal(seen.prompts,1);assert.equal(result.receipts.length,1);
    assert.equal(result.handoff_error,undefined);
    assert.deepEqual(result.handoff.outputs[0].observation_refs,[]);
    assert.match(result.handoff.limitations.join('\n'),/unverified/);
    assert.equal(result.handoff.outputs[0].summary,'Preserve the observed findings');
  }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});
test('real graph retains a safe product and unverified findings for explicit limited integration',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-limited-return-'))),previous=process.cwd();process.chdir(dir);
  const owner={thread_id:'T',work_id:'W',research_id:'research',goal_revision:1};
  const seen={returnValue:()=>({schema:'capstone-task-return/1',outputs:[
    {slot:'file',summary:'Useful saved research',scope:'Actual task',observations:[],files:[{path:'report.txt',role:'primary'}]},
    {slot:'finding',summary:'Uncertain interpretation retained',scope:'Actual task',observations:['o99'],files:[]}],
    checks:[{check:1,status:'passed',observations:['o99'],explanation:'Producer check claim'}],limitations:[]})};
  const config={researchTaskId:'task',researchAttemptId:'attempt',researchOwner:owner,model:'fake',extensions:[],allowedSkills:[],settings:{},
    applicationPolicy:{allowed_tools:['write']},researchRuntime:{isolatedTaskExecution:true,lightweightTaskNodes:true,goalDrivenExecution:true,graphWorkEdition:'capstone-graph-work/1',
      graphWork:{schema:'capstone-graph-work/1',mode:'off'},
      graphLimits:{maxNodes:8,maxItems:64,maxText:4096,maxExecutions:32,snapshotBytes:500000,publicBytes:100000},delegation:{concurrency:1,maxTurns:4,graceTurns:1}}};
  let view={research_revision:0,state:null},freezes=0;
  const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk(seen),{getModel:()=>({id:'fake'})},{skills:[],emit:()=>{},
    contextClient:{freeze:async({action})=>{freezes++;return {products:[{ref:'product-safe',path:'context-results/report.txt',sha256:'a'.repeat(64),bytes:13,
      status:'ready',roles:['primary'],owner,attempt_id:'attempt',action_id:action.id}],selections:[{path:'report.txt',ref:'product-safe'}]};}}});
  const controller=createEnterpriseGraphController({config,readResearch:async()=>structuredClone(view),
    commitResearch:async(id,request)=>{view={research_revision:view.research_revision+1,state:{...(view.state??{}),...request.changes,
      notes:[...(view.state?.notes??[]),...request.changes.notes]}};return {details:{ok:true,result:{status:'committed',receipt:{research_revision:view.research_revision}}}};},
    inspectProducts:async({products})=>({ready:true,products}),resolveInputs:async()=>({manifests:[],handles:[]}),dispatchNode:dispatch});
  try{
    const declared={id:'A',purpose:'One research turn',instruction:'Return the useful draft',questions:['What is known?'],checks:['Verify claim'],
      depends_on:[],expected_outputs:['Research draft'],mode:'execute',execution:'delegated',source_refs:[],inputs:[],
      outputs:[{slot:'file',kind:'artifact',description:'Draft'},{slot:'finding',kind:'observation',description:'Interpretation'}]};
    const planned=await controller.execute('plan','plan',{goal:'Research the supplied question',output_mode:'text',source_refs:[],nodes:[declared],
      requirements:[{id:'draft',description:'Useful research draft',kind:'artifact'},{id:'interpretation',description:'Supported interpretation',kind:'finding'}]});
    assert.equal(planned.details.ok,true,JSON.stringify(planned));
    let state;
    for(let i=0;i<100;i++){state=await controller.readState();if(state.graph.nodes[0].phase==='executed')break;await new Promise(resolve=>setTimeout(resolve,2));}
    assert.equal(state.graph.nodes[0].phase,'executed');assert.equal(seen.prompts,1);
    const proposal=await controller.readProposal(state.graph.nodes[0].execute_action_id);
    assert.match(proposal.output,/Uncertain interpretation retained/);
    const association=state.pending_proposals[0].proposal;
    assert.equal(association.status,'incomplete');
    assert.deepEqual(association.missing_slots,['finding']);
    assert.equal(association.checks[0].status,'not_run');
    assert.equal(association.outputs[0].artifact_refs[0],'product-safe');
    const recorded=await controller.execute('record','limited-record',{action_id:proposal.action.id,outcome:'limited',
      outputs:association.outputs,limitations:['Interpretation lacks admitted support']});
    assert.equal(recorded.details.ok,true,JSON.stringify(recorded));
    state=await controller.readState();
    const assessed=await controller.execute('assess','limited-assess',{action_id:state.graph.nodes[0].assess_action_id,outcome:'limited',
      checks:association.checks,summary:'Useful draft retained with uncertainty for user review'});
    assert.equal(assessed.details.ok,true,JSON.stringify(assessed));
    state=await controller.readState();
    const resultRef=state.graph.results[0].result_ref;
    const reviewed=await controller.execute('assess','turn-review',{goal_review:{decision:'limited',requirements:[
      {id:'draft',status:'satisfied',result_refs:[resultRef],explanation:'Actual saved draft'},
      {id:'interpretation',status:'open',result_refs:[],explanation:'Unverified interpretation retained for discussion'}],summary:'Deliver the useful draft with uncertainty'}});
    assert.equal(reviewed.details.ok,true,JSON.stringify(reviewed));
    const finished=await controller.finish('turn-finish',{outcome:'limited',goal_review_ref:reviewed.details.result.organization.review.review_ref,
      delivery_result_refs:[resultRef],delivery_product_refs:['product-safe'],limitations:['Interpretation remains unverified'],summary:'Draft delivered for user review'});
    assert.equal(finished.details.ok,true,JSON.stringify(finished));
    assert.equal(await controller.continuationState(),null);
    assert.equal(seen.prompts,1);
    assert.equal(freezes,1);
  }finally{await controller.close();process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});
test('lightweight semantic metadata errors do not discard safe saved products or ask the child to repeat',async()=>{
  for(const foreign of [false,true]){
    const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-retain-files-'))),previous=process.cwd();process.chdir(dir);
    const declared={...node,checks:['Inspect saved bytes'],outputs:[{slot:'file',kind:'artifact',description:'Actual saved work'}]};
    const seen={returnValue:()=>({schema:'capstone-task-return/1',outputs:[{slot:'file',summary:'Useful completed analysis',scope:'Actual task',
      observations:[],files:[{path:'report.txt',role:'data'}]}],checks:[{check:99,status:'passed',observations:[],explanation:'Mismatched check number'}],
      limitations:[],...(foreign?{binding:{action_id:'foreign-action'}}:{})})};
    const config={researchTaskId:'task',model:'fake',extensions:[],allowedSkills:[],settings:{},contextFiles:[],applicationPolicy:{allowed_tools:['write']},
      researchRuntime:{lightweightTaskNodes:true,delegation:{maxTurns:4,graceTurns:1}}};
    let freezes=0;
    try{
      const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk(seen),{getModel:()=>({id:'fake'})},{skills:[],emit:()=>{},
        contextClient:{freeze:async request=>{freezes++;assert.deepEqual(request.selection.products,[{path:'report.txt',role:'support'}]);
          return {products:[{ref:'retained-product'}],selections:[{path:'report.txt',ref:'retained-product'}]};}}});
      const result=await dispatch({action:{...action,definition_ref:'definition-A',execution_revision:1},node:declared,inputs:{manifests:[],handles:[]},
        checkpoint,contract_schema:'capstone-node-contract/1'},{validateProposal:()=>assert.fail('Invalid metadata cannot become an admitted proposal')});
      assert.equal(seen.prompts,1);assert.equal(freezes,1);
      assert.deepEqual(result.products,[{ref:'retained-product'}]);assert.equal(result.handoff,undefined);
      assert.equal(result.handoff_error.status,'rejected');assert.equal(result.handoff_error.diagnostic.stage,'association');
      assert.match(result.output,/Useful completed analysis/);
    }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
  }
});
test('definite proposal feedback repairs the original child before close without freezing an unsupported check',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-feedback-'))),previous=process.cwd();process.chdir(dir);
  const selected={...action,definition_ref:'definition-A',execution_revision:1},declared={...node,checks:['EXACT CHECK'],outputs:[{slot:'file',kind:'artifact',description:'Saved file'}]};
  const seen={manifestOnlyCorrection:true,propose(prompt,result){
    const original=seen.contract??=JSON.parse(prompt.split('\n').find(line=>line.startsWith('Committed node contract: ')).slice('Committed node contract: '.length));
    if(seen.prompts===2){assert.match(prompt,/check_support_missing/);assert.match(prompt,/EXACT CHECK/);assert.equal(seen.disposed,undefined);}
    const ref=result.content.at(-1).text.slice('Host observation reference: '.length);
    return {schema:'capstone-node-proposal/1',binding:original.binding,outputs:[{slot:'file',product_paths:['report.txt'],observation_refs:[ref],summary:'Saved',scope:'Assigned'}],
      checks:[{description:'EXACT CHECK',status:'passed',refs:seen.prompts===1?[]:[ref],explanation:'Actual observation'}],limitations:[]};
  }};
  const config={researchTaskId:'task',model:'fake',extensions:[],allowedSkills:[],settings:{},contextFiles:[],applicationPolicy:{allowed_tools:['write']},researchRuntime:{delegation:{maxTurns:4,graceTurns:1}}};
  let freezes=0,validations=0;const frames=[];
  try{
    const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk(seen),{getModel:()=>({id:'fake'})},{skills:[],emit:frame=>frames.push(frame),contextClient:{freeze:async()=>{
      freezes++;return {products:[{ref:'product-file'}],selections:[{path:'report.txt',ref:'product-file'}]};
    }}});
    const result=await dispatch({action:selected,node:declared,inputs:{manifests:[],handles:[]},checkpoint,contract_schema:'capstone-node-contract/1'},
      {validateProposal:candidate=>{validations++;if(!candidate.handoff.checks[0].refs.length)throw Object.assign(new Error('A passed check needs admitted support'),
        {diagnostic:{code:'check_support_missing',field:'checks[0].refs',check_label:'EXACT CHECK',valid_refs:candidate.receipts.map(item=>item.ref)}});}});
    assert.equal(seen.prompts,2);assert.equal(seen.closes,1);assert.equal(freezes,1);assert.ok(validations>=3);
    assert.equal(result.status,'completed');assert.deepEqual(result.handoff.outputs[0].artifact_refs,['product-file']);
    assert.equal(result.proposal_diagnostics.length,1);assert.equal(result.proposal_diagnostics[0].code,'check_support_missing');
    assert.equal(frames.filter(frame=>frame.type==='enterprise_graph_child_response').length,2);
  }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});
test('child proposal correction keeps one lifetime budget and exact freeze identities',async()=>{
  for(const mode of ['valid','repeated','unknown','changed-bytes','budget','cancel','selection_invalid','action_unavailable','owner_invalid','source_unavailable','unrecognized_rejection']){
    const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-feedback-boundary-'))),previous=process.cwd();process.chdir(dir);
    const selected={...action,definition_ref:'definition-A',execution_revision:1},declared={...node,checks:['CHECK'],outputs:[{slot:'file',kind:'artifact',description:'Saved file'}]};
    const abort=new AbortController(),freezes=[],frames=[];
    const seen={reportText:round=>'actual bytes '+round,beforePrompt(){if(mode==='cancel'&&seen.prompts===2)abort.abort();},propose(prompt,result){
      const contract=seen.contract??=JSON.parse(prompt.split('\n').find(line=>line.startsWith('Committed node contract: ')).slice('Committed node contract: '.length));
      const ref=result.content.at(-1).text.slice('Host observation reference: '.length);
      return {schema:'capstone-node-proposal/1',binding:contract.binding,outputs:[{slot:'file',product_paths:['report.txt'],observation_refs:[ref],summary:'Saved',scope:'Assigned'}],
        checks:[{description:'CHECK',status:'passed',refs:['repeated','budget','cancel'].includes(mode)?[]:[ref],explanation:'Changed explanation '+seen.prompts}],limitations:[]};
    }};
    const config={researchTaskId:'task',model:'fake',extensions:[],allowedSkills:[],settings:{},contextFiles:[],applicationPolicy:{allowed_tools:['write']},
      researchRuntime:{delegation:{maxTurns:mode==='budget'?1:4,graceTurns:1}}};
    try{
      const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk(seen),{getModel:()=>({id:'fake'})},{skills:[],emit:frame=>frames.push(frame),contextClient:{freeze:async(_request,control)=>{
        freezes.push(control.requestKey);
        if(mode==='unknown')throw Object.assign(new Error('Transport uncertain'),{category:'unknown',request_id:'ctx-exact-unknown'});
        if(mode==='selection_invalid'&&freezes.length===1)throw Object.assign(new Error('Correct actual selection'),{category:'rejected',request_id:'ctx-selection-rejected',rejection_code:mode});
        if(['action_unavailable','owner_invalid','source_unavailable','unrecognized_rejection'].includes(mode))
          throw Object.assign(new Error('Host authority rejected the request'),{category:'rejected',request_id:'ctx-authority-rejected',rejection_code:mode});
        const bytes=await readFile(join(seen.options.cwd,'report.txt')),ref='product-'+createHash('sha256').update(bytes).digest('hex');
        return {products:[{ref}],selections:[{path:'report.txt',ref}]};
      }}});
      const result=await dispatch({action:selected,node:declared,inputs:{manifests:[],handles:[]},checkpoint,contract_schema:'capstone-node-contract/1'},
        {signal:abort.signal,validateProposal:candidate=>{
          if(!candidate.handoff.checks[0].refs.length)throw Object.assign(new Error('Support missing'),{diagnostic:{code:'check_support_missing',field:'checks[0].refs',check_label:'CHECK',valid_refs:candidate.receipts.map(item=>item.ref)}});
          if(mode==='changed-bytes'&&!candidate.metadata&&freezes.length===1)throw Object.assign(new Error('Correct association'),{diagnostic:{code:'output_support',field:'outputs'}});
        }});
      assert.equal(seen.closes,1,mode);
      const responses=frames.filter(frame=>frame.type==='enterprise_graph_child_response');
      assert.equal(responses.length,seen.prompts-(mode==='cancel'?1:0),mode);
      assert.equal(responses.reduce((n,frame)=>n+frame.usage.totalTokens,0),responses.length*5,mode);
      if(mode==='valid'){assert.equal(seen.prompts,1);assert.equal(freezes.length,1);assert.equal(result.proposal_diagnostics,undefined);}
      if(mode==='repeated'){assert.equal(seen.prompts,2);assert.equal(freezes.length,0);assert.equal(result.proposal_diagnostics.length,2);assert.equal(result.handoff_error.status,'rejected');assert.equal(result.status,'completed');}
      if(mode==='budget'){assert.equal(seen.prompts,1);assert.equal(seen.steered,true);assert.equal(freezes.length,0);assert.equal(result.handoff_error.status,'rejected');}
      if(mode==='unknown'){assert.equal(seen.prompts,1);assert.equal(freezes.length,1);assert.equal(result.persistence.status,'unknown');assert.equal(result.persistence.request_id,'ctx-exact-unknown');assert.equal(result.proposal_diagnostics,undefined);assert.equal(result.handoff,undefined);}
      if(mode==='selection_invalid'){assert.equal(seen.prompts,2);assert.equal(freezes.length,2);assert.notEqual(freezes[0],freezes[1]);assert.equal(result.proposal_diagnostics[0].code,'selection_invalid');assert.ok(result.handoff);}
      if(['action_unavailable','owner_invalid','source_unavailable','unrecognized_rejection'].includes(mode)){
        assert.equal(seen.prompts,1,mode);assert.equal(freezes.length,1,mode);assert.equal(result.status,'completed');
        assert.equal(result.persistence.status,'rejected');assert.equal(result.persistence.request_id,'ctx-authority-rejected');
        assert.equal(result.persistence.rejection_code,mode==='unrecognized_rejection'?'host_rejected':mode);
        assert.equal(result.persistence.recovery,'stop_current_action');assert.match(result.output,/Do not retry this child identity/);
        assert.equal(result.proposal_diagnostics[0].code,result.persistence.rejection_code);
        assert.equal(result.handoff,undefined);assert.equal(await readFile(join(seen.options.cwd,'report.txt'),'utf8'),'actual bytes 1');
      }
      if(mode==='changed-bytes'){
        assert.equal(seen.prompts,2);assert.equal(freezes.length,2);assert.notEqual(freezes[0],freezes[1]);
        assert.equal(result.handoff.outputs[0].artifact_refs[0],'product-'+createHash('sha256').update('actual bytes 2').digest('hex'));
      }
      if(mode==='cancel'){assert.equal(seen.prompts,2);assert.equal(result.status,'cancelled');assert.equal(freezes.length,0);assert.equal(seen.aborted,true);}
    }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
  }
});
test('new child protocol receives exact slots/checks and maps paths through host freeze selections',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-contract-'))),previous=process.cwd();process.chdir(dir);
  const selected={...action,definition_ref:'definition-A',execution_revision:3},declared={...node,purpose:'Only assigned work',checks:['EXACT CHECK'],
    outputs:[{slot:'table',kind:'artifact',description:'EXACT SLOT DESCRIPTION'}]};
  const seen={propose(prompt,result){
    const contract=JSON.parse(prompt.split('\n').find(line=>line.startsWith('Committed node contract: ')).slice('Committed node contract: '.length));
    assert.deepEqual(contract.outputs,declared.outputs);assert.deepEqual(contract.checks,declared.checks);
    assert.deepEqual(contract.source_files,[]);
    assert.deepEqual(contract.product_manifest_template,{schema:'capstone-workspace-products/1',products:[],graph_proposal:{
      schema:'capstone-node-proposal/1',binding:contract.binding,
      outputs:[{slot:'table',product_paths:[],observation_refs:[],summary:'',scope:''}],
      checks:[{description:'EXACT CHECK',status:'not_run',refs:[],explanation:''}],limitations:[]}});
    assert.match(prompt,/product_manifest_template/);
    assert.equal(contract.definition_ref,selected.definition_ref);assert.equal(contract.execution_revision,3);
    return {schema:'capstone-node-proposal/1',binding:contract.binding,outputs:[{slot:'table',product_paths:['report.txt'],
      observation_refs:[result.details.native_research_source.source_ref],summary:'Actual table',scope:'Assigned scope'}],
      checks:[{description:'EXACT CHECK',status:'passed',refs:[result.details.native_research_source.source_ref],explanation:'Actual write'}],limitations:[]};
  }};
  const config={researchTaskId:'task',researchAttemptId:'attempt',researchOwner:selected.owner,model:'fake',extensions:[],allowedSkills:[],settings:{},
    contextFiles:[],applicationPolicy:{allowed_tools:['write']},researchRuntime:{delegation:{maxTurns:4,graceTurns:1}}};
  const product={ref:'product-exact',path:'context-results/opaque/report.txt',sha256:'a'.repeat(64),bytes:13,roles:['primary'],status:'ready',
    owner:selected.owner,attempt_id:'attempt',action_id:selected.id};
  try{
    const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk(seen),{getModel:()=>({id:'fake'})},{skills:[],emit:()=>{},
      contextClient:{freeze:async()=>({ready:true,products:[product],selections:[{path:'report.txt',ref:product.ref}]})}});
    const result=await dispatch({action:selected,node:declared,inputs:{manifests:[],handles:[]},checkpoint,contract_schema:'capstone-node-contract/1'});
    const contractFile=join(dir,'.research-workers',createHash('sha256').update(selected.id).digest('hex'),'.capstone-node-contract.json');
    assert.equal((await stat(contractFile)).mode&0o222,0);
    assert.deepEqual(JSON.parse(await readFile(contractFile,'utf8')).binding,result.handoff.binding);
    assert.ok(seen.prompt.includes(contractFile));
    assert.equal(result.status,'completed');assert.deepEqual(result.handoff.outputs[0].artifact_refs,[product.ref]);
    assert.equal(result.handoff.outputs[0].product_paths,undefined);assert.deepEqual(result.handoff.binding.consumed_results,[]);
    assert.equal(result.handoff.checks[0].description,'EXACT CHECK');
  }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});
test('new contract keeps completed native status separate from a definite saved-product rejection',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-persistence-status-'))),previous=process.cwd();process.chdir(dir);
  const config={researchTaskId:'task',model:'fake',extensions:[],allowedSkills:[],settings:{},contextFiles:[],applicationPolicy:{allowed_tools:['write']},
    researchRuntime:{delegation:{maxTurns:4,graceTurns:1}}};
  try{
    const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk({}),{getModel:()=>({id:'fake'})},{skills:[],emit:()=>{},contextClient:{freeze:async()=>{
      throw Object.assign(new Error('Unsafe /private/host-detail'),{category:'rejected',code:'graph_context_rejected',request_id:'ctx-rejected',operation:'freeze',rejection_code:'selection_invalid'});
    }}});
    const result=await dispatch({action:{...action,definition_ref:'definition-A',execution_revision:1},node:{...node,outputs:[],checks:[]},
      inputs:{manifests:[],handles:[]},checkpoint,contract_schema:'capstone-node-contract/1'});
    assert.equal(result.status,'completed');assert.equal(result.persistence.status,'rejected');assert.equal(result.persistence.request_id,'ctx-rejected');
    assert.match(result.output,/definitively rejected/);assert.doesNotMatch(result.output,/not confirmed|\/private\/host-detail/);
    assert.equal(await readFile(join(dir,'.research-workers',createHash('sha256').update(action.id).digest('hex'),'report.txt'),'utf8'),'actual report');
  }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});
test('malformed local product manifests are definite rejections without a recoverable host request',async()=>{
  for(const manifestText of ['{invalid',JSON.stringify({schema:'unknown',products:[]}),
    JSON.stringify({schema:'capstone-workspace-products/1',products:'invalid'}),
    JSON.stringify({schema:'capstone-workspace-products/1',products:[{path:'report.txt',role:'invalid'}]})]){
    const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-local-manifest-'))),previous=process.cwd();process.chdir(dir);
    let freezeCalls=0;
    const config={researchTaskId:'task',model:'fake',extensions:[],allowedSkills:[],settings:{},contextFiles:[],applicationPolicy:{allowed_tools:['write']},
      researchRuntime:{delegation:{maxTurns:4,graceTurns:1}}};
    try{
      const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk({manifestText}),{getModel:()=>({id:'fake'})},{skills:[],emit:()=>{},
        contextClient:{freeze:async()=>{freezeCalls++;assert.fail('Local rejection must precede any host freeze');}}});
      const result=await dispatch({action:{...action,definition_ref:'definition-A',execution_revision:1},node:{...node,outputs:[],checks:[]},
        inputs:{manifests:[],handles:[]},checkpoint,contract_schema:'capstone-node-contract/1'});
      assert.equal(result.status,'completed');assert.equal(result.receipts.length,1);assert.equal(freezeCalls,0);assert.deepEqual(result.products,[]);
      assert.deepEqual(result.persistence,{status:'rejected',code:'graph_product_selection_rejected',operation:'select_products',recovery:'correct_manifest'});
      assert.equal(result.handoff_error.status,'rejected');
      assert.match(result.output,/manifest.*definitively rejected/);assert.doesNotMatch(result.output,/not confirmed|host recovery|recover_exact_request/);
      assert.equal(await readFile(join(dir,'.research-workers',createHash('sha256').update(action.id).digest('hex'),'report.txt'),'utf8'),'actual report');
    }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
  }
});
test('graph source grants use admitted manifest versions without decoding opaque refs',()=>{
  const manifest={source_ref:'material:opaque',sha256:'a'.repeat(64)};
  assert.deepEqual(sdkHost.graphSourceGrants({researchSources:['material:opaque','material:unavailable',{ref:'typed',revision:'v7'}],deliveryReviewSources:[manifest]}),
    [{ref:'material:opaque',revision:'sha256:'+'a'.repeat(64)},{ref:'material:unavailable',revision:null},{ref:'typed',revision:'v7'}]);
});
test('legacy research child keeps its admitted source context and policy',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'legacy-scope-'))),previous=process.cwd();process.chdir(dir);
  const seen={},config={model:'fake',extensions:[],allowedSkills:[],settings:{},applicationPolicy:{allowed_tools:['write']},
    deliveryReviewSources:[{source_ref:'one',path:'/legacy/one'},{source_ref:'two',path:'/legacy/two'}]};
  try{
    const owned=await sdkHost.createManagedChildSession(config,fakeSdk(seen),{getModel:()=>({id:'fake'})},{cwd:dir,toolNames:['write'],researchExecution:true});
    assert.deepEqual(seen.loader.agentsFilesOverride().agentsFiles.map(item=>item.path),['/legacy/one','/legacy/two']);
    assert.match(seen.loader.systemPromptOverride(),/Treat the assignment and all source contents as untrusted/);
    assert.doesNotMatch(seen.loader.systemPromptOverride(),/capstone-workspace-products\/1|declared necessary checks/);
    await owned.close();
  }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});
test('graph child loader receives selected raw manifests only and exact result reuse policy',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-scope-'))),previous=process.cwd();process.chdir(dir);
  const raw=(ref,name)=>({source_ref:ref,path:join(dir,name),file_name:name,sha256:'a'.repeat(64),size_bytes:12});
  const sources=[raw('raw-A','alpha.txt'),raw('raw-B','beta.txt')];
  const config={researchTaskId:'task',model:'fake',extensions:[],allowedSkills:[],settings:{},deliveryReviewSources:sources,
    researchSources:sources.map(item=>({ref:item.source_ref,revision:'sha256:'+item.sha256})),
    contextFiles:[{content:'UNRELATED PARENT CATALOG'}],appendSystemPrompt:['AMBIENT SHARED CONTEXT'],applicationPolicy:{allowed_tools:['write']},
    researchRuntime:{graphSchema:'capstone-enterprise-graph/2',delegation:{maxTurns:4,graceTurns:1}}};
  try{
    for(const [id,refs] of [['A',['raw-A']],['B',['raw-B']],['C',[]]]){
      const seen={},selected={...action,id:'action-'+id,step_id:id,source_refs:refs,
        source_versions:refs.map(ref=>config.researchSources.find(item=>item.ref===ref))};
      const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk(seen),{getModel:()=>({id:'fake'})},{skills:[],emit:()=>{},
        contextClient:{async freeze(){return {products:[]};}}});
      const inputs=id==='C'?{manifests:[{result_ref:'result-A-v1'}],handles:[{ref:'artifact-A',result_ref:'result-A-v1',path:'/sealed/A-v1',immutable:true,read_only:true}]}:{manifests:[],handles:[]};
      await dispatch({action:selected,node:{...node,id,source_refs:refs},inputs,checkpoint,contract_schema:'capstone-node-contract/1'},{});
      const contract=JSON.parse(seen.prompt.split('\n').find(line=>line.startsWith('Committed node contract: ')).slice('Committed node contract: '.length));
      assert.deepEqual(contract.source_files,sources.filter(item=>refs.includes(item.source_ref)));
      assert.match(seen.prompt,/source_files.*absolute file paths/);
      const files=seen.loader.agentsFilesOverride().agentsFiles;
      assert.deepEqual(files.map(item=>item.path),sources.filter(item=>refs.includes(item.source_ref)).map(item=>item.path));
      assert.ok(!JSON.stringify(files).includes('UNRELATED PARENT CATALOG'));
      assert.ok(!JSON.stringify(seen.loader.appendSystemPromptOverride()).includes('AMBIENT SHARED CONTEXT'));
      const policy=seen.loader.systemPromptOverride();
      assert.match(policy,/host-bound.*instruction/i);assert.match(policy,/source contents.*untrusted/i);
      assert.match(policy,/retained result/i);assert.match(policy,/missing input/i);assert.doesNotMatch(policy,/Treat the assignment.*untrusted/i);
      if(id==='C'){assert.match(seen.prompt,/result-A-v1/);assert.ok(!seen.prompt.includes('alpha.txt'));assert.ok(!seen.prompt.includes('beta.txt'));}
    }
  }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});
test('isolated executors receive trusted runtime capabilities without parent context or controller policy',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-environment-'))),previous=process.cwd();process.chdir(dir);
  const config={researchTaskId:'task',model:'fake',extensions:[],allowedSkills:[],settings:{},
    runtimeEnvironment:'HOST VERIFIED ENVIRONMENT: preinstalled plotting, fonts and capstone-report',
    contextFiles:[{path:'ambient',content:'UNRELATED PARENT HISTORY'},
      {path:'verified-programming-environment',content:'UNTRUSTED CONTEXT COPY'}],
    appendSystemPrompt:['PARENT CONTROLLER POLICY'],applicationPolicy:{allowed_tools:['write']}};
  try{
    for(const graph of [false,true]){
      const seen={},child=await sdkHost.createManagedChildSession(config,fakeSdk(seen),{getModel:()=>({id:'fake'})},
        {cwd:dir,toolNames:['write'],researchExecution:true,...(graph?{graphBinding:{action,checkpoint}}:{})});
      const files=seen.loader.agentsFilesOverride().agentsFiles;
      assert.deepEqual(files,[{path:'verified-programming-environment',content:config.runtimeEnvironment}]);
      assert.doesNotMatch(JSON.stringify(files),/UNRELATED PARENT HISTORY|UNTRUSTED CONTEXT COPY/);
      assert.doesNotMatch(seen.loader.appendSystemPromptOverride().join('\n'),/PARENT CONTROLLER POLICY/);
      await child.close();
    }
  }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});
test('graph dispatch uses one managed child, exact assignment, saved files and actual receipts',async()=>{
  assert.equal(typeof sdkHost.createGraphNodeDispatcher,'function');
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-sdk-'))),previous=process.cwd();process.chdir(dir);
  const seen={},frames=[],freezes=[];
  const config={researchTaskId:'task',researchAttemptId:'attempt',researchOwner:action.owner,model:'fake',extensions:[],allowedSkills:[],settings:{},
    contextFiles:[{content:'PARENT HISTORY MUST NOT APPEAR'}],applicationPolicy:{allowed_tools:['write']},researchRuntime:{isolatedTaskExecution:true,delegation:{maxTurns:4,graceTurns:1}}};
  const product={ref:'workspace-product:actual',path:'context-results/frozen/report.txt',sha256:'a'.repeat(64),bytes:13,roles:['primary'],status:'ready',owner:action.owner,attempt_id:'attempt',action_id:action.id};
  const contextClient={async freeze(args){freezes.push(args);return {ready:true,products:[product]};}};
  try{
    const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk(seen),{getModel:()=>({id:'fake'})},{skills:[],contextClient,emit:frame=>frames.push(frame)});
    const inputs={manifests:[{result_ref:'selected-v1'}],handles:[{ref:'artifact-v1',result_ref:'selected-v1',immutable:true,read_only:true,path:'/host/sealed/v1'}]};
    const result=await dispatch({action,node,inputs,checkpoint},{});
    assert.equal(result.status,'completed');assert.equal(result.output,'Observed result proposal');assert.deepEqual(result.products,[product]);
    assert.equal(result.receipts.length,1);assert.equal(result.receipts[0].action_id,action.id);
    assert.equal(seen.options.cwd,join(dir,'.research-workers',createHash('sha256').update(action.id).digest('hex')));
    assert.ok(seen.prompt.includes('EXACT INSTRUCTION'));assert.ok(seen.prompt.includes('EXACT QUESTION'));assert.ok(seen.prompt.includes('EXACT OUTPUT'));
    assert.ok(seen.prompt.includes('/host/sealed/v1'));assert.ok(!seen.prompt.includes('PARENT HISTORY'));
    assert.deepEqual(freezes[0].selection,{products:[{path:'report.txt',role:'primary'}]});
    const end=frames.find(frame=>frame.type==='enterprise_graph_child_tool'&&frame.activity==='end');
    assert.ok(Number.isFinite(end.execution_ms)&&end.execution_ms>=0,
      'The executor measures tool execution before transport and persistence');
    assert.equal(end.result.details.native_research_source.source_ref,result.receipts[0].ref);
    assert.ok(frames.some(frame=>frame.type==='enterprise_graph_child_response'&&frame.usage?.totalTokens===5));
    assert.equal(seen.disposed,true);
  }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});
test('owned graph child cancellation waits for abort and disposal',async()=>{
  assert.equal(typeof sdkHost.createGraphNodeDispatcher,'function');
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-sdk-'))),previous=process.cwd();process.chdir(dir);
  const seen={},abort=new AbortController();
  const config={researchTaskId:'task',researchAttemptId:'attempt',researchOwner:action.owner,model:'fake',extensions:[],allowedSkills:[],settings:{},applicationPolicy:{allowed_tools:['write']},researchRuntime:{delegation:{maxTurns:4,graceTurns:1}}};
  try{
    const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk(seen,{block:true}),{getModel:()=>({id:'fake'})},{skills:[],contextClient:{freeze:()=>assert.fail('no products')},emit:()=>{}});
    const task=dispatch({action,node,inputs:{manifests:[],handles:[]},checkpoint},{signal:abort.signal});
    while(!seen.prompt)await new Promise(resolve=>setTimeout(resolve,1));
    abort.abort();const result=await task;
    assert.equal(result.status,'cancelled');assert.equal(seen.aborted,true);assert.equal(seen.disposed,true);
  }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});

test('graph child cannot read a symlinked product declaration outside its cwd',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-marker-'))),previous=process.cwd();process.chdir(dir);
  const config={researchTaskId:'task',researchAttemptId:'attempt',researchOwner:action.owner,model:'fake',extensions:[],allowedSkills:[],settings:{},applicationPolicy:{allowed_tools:['write']},researchRuntime:{delegation:{maxTurns:4,graceTurns:1}}};
  const frames=[],sdk=fakeSdk({}),create=sdk.createAgentSession;
  sdk.createAgentSession=async options=>{
    const owned=await create(options),prompt=owned.session.prompt;
    owned.session.prompt=async text=>{await prompt(text);await rm(join(options.cwd,'.capstone-products.json'));await symlink(join(dir,'outside.json'),join(options.cwd,'.capstone-products.json'));};return owned;
  };
  try{
    await writeFile(join(dir,'outside.json'),JSON.stringify({schema:'capstone-workspace-products/1',products:[]}));
    const dispatch=sdkHost.createGraphNodeDispatcher(config,sdk,{getModel:()=>({id:'fake'})},{skills:[],contextClient:{freeze:()=>assert.fail('unsafe declaration')},emit:frame=>frames.push(frame)});
    const result=await dispatch({action,node,inputs:{manifests:[],handles:[]},checkpoint},{});
    assert.equal(result.status,'failed');assert.deepEqual(result.products,[]);
    assert.match(result.output,/local saved-product manifest.*definitively rejected/);
    assert.equal(result.persistence.recovery,'correct_manifest');assert.equal(result.persistence.request_id,undefined);
    const terminal=frames.filter(frame=>frame.type==='enterprise_graph_child_finished');
    assert.equal(terminal.length,1);assert.equal(terminal[0].status,'failed');
    assert.ok(!JSON.stringify(terminal).includes('ELOOP'));assert.ok(!JSON.stringify(terminal).includes(dir));
  }finally{process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});

test('close drains a cancelled child with saved bytes and a missing freeze receipt',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-freeze-cancel-'))),previous=process.cwd();process.chdir(dir);
  const owner={thread_id:'thread',work_id:'work',research_id:'research',goal_revision:1};
  const config={researchTaskId:'task',researchAttemptId:'attempt',researchOwner:owner,model:'fake',extensions:[],allowedSkills:[],settings:{},
    deadlineAt:Date.now()+60000,applicationPolicy:{allowed_tools:['write']},researchRuntime:{
      graphLimits:{maxNodes:8,maxItems:64,maxText:4096,maxExecutions:32,snapshotBytes:500000,publicBytes:100000},delegation:{concurrency:1,maxTurns:4,graceTurns:1}}};
  const seen={},frames=[];let view={research_revision:0,state:null},releaseFreeze,freezeSignal,timer;
  const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk(seen,{block:true,saveBeforeBlock:true}),{getModel:()=>({id:'fake'})},
    {skills:[],emit:frame=>frames.push(frame),contextClient:{freeze:(_,{signal}={})=>{
      freezeSignal=signal;
      return new Promise((resolve,reject)=>{
        releaseFreeze=()=>resolve({products:[]});
        if(signal?.aborted)reject(signal.reason);
        else signal?.addEventListener('abort',()=>reject(signal.reason),{once:true});
      });
    }}});
  const controller=createEnterpriseGraphController({config,readResearch:async()=>structuredClone(view),
    commitResearch:async(id,request)=>{view={research_revision:view.research_revision+1,state:{...(view.state??{}),...request.changes,
      notes:[...(view.state?.notes??[]),...request.changes.notes]}};return {details:{ok:true,result:{status:'committed',receipt:{research_revision:view.research_revision}}}};},
    inspectProducts:async({products})=>({ready:true,products}),dispatchNode:dispatch,resolveInputs:async()=>({manifests:[],handles:[]})});
  let closing;
  try{
    const child={id:'A',purpose:'Inspect source',questions:['What is saved?'],checks:['Check source'],depends_on:[],expected_outputs:['Saved report'],
      mode:'execute',execution:'delegated',instruction:'Save a report',source_refs:[],outputs:[{slot:'value',kind:'observation',description:'Report'}],inputs:[]};
    assert.equal((await controller.execute('plan','plan',{goal:'Inspect source',output_mode:'text',source_refs:[],nodes:[child]})).details.ok,true);
    while(!seen.saved)await new Promise(resolve=>setTimeout(resolve,1));
    closing=controller.close({reason:'Cancel child'});
    const outcome=await Promise.race([closing.then(()=> 'drained'),new Promise(resolve=>{timer=setTimeout(()=>resolve('blocked'),100);})]);
    assert.equal(outcome,'drained');assert.equal(freezeSignal,undefined);
    assert.equal(seen.aborted,true);assert.equal(seen.disposed,true);
    const state=await controller.readState();assert.equal(state.graph.nodes[0].settled_status,'cancelled');
    assert.match((await controller.readProposal(state.graph.nodes[0].execute_action_id)).output,/completion was cancelled/);
    const terminal=frames.filter(frame=>frame.type==='enterprise_graph_child_finished');
    assert.equal(terminal.length,1);assert.equal(terminal[0].status,'cancelled');
    assert.match(terminal[0].result_summary,/completion was cancelled/);
  }finally{clearTimeout(timer);releaseFreeze?.();await closing;process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});

test('abort during actual context receipt polling keeps native text and returns a persistence limitation',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-receipt-cancel-'))),previous=process.cwd();process.chdir(dir);
  const abort=new AbortController(),seen={},frames=[],requests=[];
  const config={researchTaskId:'task',researchAttemptId:'attempt',researchOwner:action.owner,model:'fake',extensions:[],allowedSkills:[],settings:{},
    graphContextPath:join(dir,'context'),deadlineAt:Date.now()+60000,applicationPolicy:{allowed_tools:['write']},researchRuntime:{delegation:{maxTurns:4,graceTurns:1}}};
  const client=createGraphContextClient(config,{emit:request=>requests.push(request)});
  const dispatch=sdkHost.createGraphNodeDispatcher(config,fakeSdk(seen),{getModel:()=>({id:'fake'})},{skills:[],contextClient:client,emit:frame=>frames.push(frame)});
  let task;
  try{
    task=dispatch({action,node,inputs:{manifests:[],handles:[]},checkpoint},{signal:abort.signal});
    while(!requests.length)await new Promise(resolve=>setTimeout(resolve,1));
    abort.abort();const result=await task;
    assert.equal(requests.length,1);assert.equal(requests[0].operation,'freeze');
    assert.equal(result.status,'cancelled');assert.deepEqual(result.products,[]);
    assert.match(result.output,/Observed result proposal/);assert.match(result.output,/Saved-product persistence was not confirmed/);
    assert.equal(seen.disposed,true);
    const terminal=frames.find(frame=>frame.type==='enterprise_graph_child_finished');
    assert.equal(terminal.status,'cancelled');assert.equal(terminal.model_responses,1);assert.equal(terminal.usage[0].totalTokens,5);
  }finally{abort.abort();await task;process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});

test('real SDK entry point registers graph tools without a manual delegate grant',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-route-'))),previous=process.cwd();
  const root=fileURLToPath(new URL('../../../../',import.meta.url));
  const resources=join(dir,'resources'),channel=join(dir,'channel'),context=join(dir,'context'),workspace=join(dir,'workspace');
  await cp(join(root,'packages/capstone-agent/src/capstone_agent/resources'),resources,{recursive:true,dereference:true});
  await mkdir(join(resources,'node_modules','@earendil-works'),{recursive:true});
  for(const [name,path] of [['pi-coding-agent','coding-agent'],['pi-ai','ai']])await symlink(join(root,'.grid-agent/runtime/pi/source/packages',path),join(resources,'node_modules/@earendil-works',name),'dir');
  for(const path of [channel,join(channel,'requests'),join(channel,'receipts'),context,workspace])await mkdir(path,{recursive:true});
  const identity={run_id:'run',turn_id:'turn',attempt_id:'attempt',research_id:'research'};
  const schema={type:'object',additionalProperties:false,properties:{}};
  const readSchema=JSON.parse(execFileSync(join(root,'packages/capstone-agent/.venv/bin/python'),['-c',
    'import json;from capability_agent.application.research_models import research_tool_schemas;print(json.dumps(research_tool_schemas()[0]))'],{cwd:root,encoding:'utf8'}));
  await writeFile(join(channel,'binding.json'),JSON.stringify({schema_version:'capability-research-channel/1.0',...identity,
    read_tool_schema:readSchema,update_tool_schema:{...schema,properties:{changes:{},expected_revision:{}}},progress_tool_schema:schema,depth_tool_schema:schema}));
  await writeFile(join(channel,'view.json'),JSON.stringify({schema_version:'capability-research-view/1.0',...identity,research_revision:0,state:null}));
  const registry=new Map(),observed={},frames=[];
  const sdk=fakeSdk(observed);
  sdk.DefaultResourceLoader=class{
    constructor(options){this.options=options;observed.loader=options;}
    async reload(){for(const factory of this.options.extensionFactories)factory({registerTool:tool=>registry.set(tool.name,tool),on(){}});}
    getExtensions(){return {errors:[],extensions:[]};}getSkills(){return {skills:[],diagnostics:[]};}
  };
  sdk.createAgentSession=async options=>({session:{async bindExtensions(){},setActiveToolsByName(names){observed.active=names;},getActiveToolNames(){return observed.active;},
    extensionRunner:{async emit(){observed.shutdown=true;}},dispose(){observed.disposed=true;}}});
  const config={researchTaskId:'task',researchAttemptId:'attempt',researchOwner:{thread_id:'T',work_id:'W',research_id:'research',goal_revision:1},
    model:'fake',extensions:[],allowedSkills:[],contextFiles:[],settings:{},graphContextPath:context,researchChannelPath:channel,inventoryOnly:true,
    researchRuntime:{enabled:true,isolatedTaskExecution:true,graphSchema:'capstone-enterprise-graph/2',graphLimits:{maxNodes:8,maxItems:32,maxText:2048,maxExecutions:16,snapshotBytes:100000,publicBytes:50000},delegation:{concurrency:2,maxTurns:4,graceTurns:1}},
    applicationPolicy:{allowed_tools:['write','agent_research_plan','agent_research_start','agent_research_record','agent_research_assess','agent_research_revise','agent_research_resolve','agent_research_inspect','agent_research_finish']}};
  const original=process.stdout.write;process.stdout.write=chunk=>{frames.push(JSON.parse(chunk));return true;};
  try{
    process.chdir(workspace);
    const host=await import(pathToFileURL(join(resources,'general-sdk.mjs')).href);
    await host.runManagedSession(config,sdk,{getModel:()=>({id:'fake'})});
    assert.ok(registry.has('agent_research_start'));assert.ok(registry.has('agent_research_finish'));
    assert.ok(!registry.has('agent_research_cycle'));assert.ok(!observed.active.includes('agent_delegate'));
    assert.ok(!observed.active.includes('write'));
    assert.ok(!registry.has('agent_research_inspect'));assert.ok(!observed.active.includes('agent_research_inspect'));
    assert.equal(observed.disposed,true);assert.equal(observed.shutdown,true);
    assert.equal(frames[0].type,'general_pi_inventory');
    config.researchRuntime.lightweightTaskNodes=true;
    config.systemPrompt='SELECTED APPLICATION RULES';
    config.appendSystemPrompt=['SELECTED AUTHORITY AND NETWORK POLICY'];
    config.researchSources=['material:prior'];
    config.deliveryReviewSources=[{source_ref:'material:prior',file_name:'prefix-note.md',origin:'previous_product',path:'/private/prior-note.md'},
      {source_ref:'material:unselected',file_name:'unselected.md',origin:'previous_product'}];
    await host.runManagedSession(config,sdk,{getModel:()=>({id:'fake'})});
    const prompt=observed.loader.systemPromptOverride();
    const execution=JSON.parse(prompt.split('\n').find(line=>line.startsWith('Task execution contract: ')).slice('Task execution contract: '.length));
    assert.equal(execution.max_concurrency,undefined);assert.equal(execution.task_context,'independent');
    assert.equal(execution.shared_context,'read_only');assert.equal(execution.planning,'incremental');
    assert.equal(execution.parent_updates,'explicit_task_returns');
    for(const concurrency of [1,3]){
      config.researchRuntime.delegation.concurrency=concurrency;
      const selected=JSON.parse(observed.loader.systemPromptOverride().split('\n').find(line=>line.startsWith('Task execution contract: ')).slice('Task execution contract: '.length));
      assert.deepEqual(selected,execution,'Resource capacity must not change the semantic planning contract');
    }
    config.researchRuntime.delegation.concurrency=2;
    assert.match(prompt,/task organization engine/);
    assert.match(prompt,/multiple tool calls in one model response/);
    assert.match(prompt,/next decision/);
    assert.match(prompt,/Prefer separate parallel-ready tasks for independently useful requested outcomes/);
    assert.match(prompt,/Shared read-only sources or a common preparation result are not reasons to merge/);
    assert.match(prompt,/Submit the currently justified independent tasks together in one planning batch/);
    assert.match(prompt,/Combine outcomes only when their methods or interpretation genuinely depend on each other/);
    assert.match(prompt,/Do not invent a dependency to serialize independent work/);
    assert.match(prompt,/user judges/);
    assert.match(prompt,/Do not automatically repeat/);
    assert.match(prompt,/Do not invent numeric word/);
    assert.match(prompt,/material:prior/);assert.match(prompt,/previous_product/);
    assert.doesNotMatch(prompt,/material:unselected|\/private\/prior-note/);
    assert.match(prompt,/SELECTED APPLICATION RULES/);
    const appended=observed.loader.appendSystemPromptOverride().join('\n');
    assert.match(appended,/SELECTED AUTHORITY AND NETWORK POLICY/);
    assert.doesNotMatch(appended,/Native bash uses pipefail/);
    config.researchRuntime.lightweightTaskNodes=false;
    await host.runManagedSession(config,sdk,{getModel:()=>({id:'fake'})});
    assert.equal(observed.loader.systemPromptOverride(),'SELECTED APPLICATION RULES');
  }finally{process.stdout.write=original;process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});

test('actual managed child dispatch releases C after model acceptance of A while B still runs',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-schedule-'))),previous=process.cwd();process.chdir(dir);
  const owner={thread_id:'thread',work_id:'work',research_id:'research',goal_revision:1};
  const config={researchTaskId:'task',researchAttemptId:'attempt',researchOwner:owner,model:'fake',extensions:[],allowedSkills:[],settings:{},
    applicationPolicy:{allowed_tools:['write']},researchRuntime:{graphLimits:{maxNodes:8,maxItems:64,maxText:4096,maxExecutions:32,snapshotBytes:500000,publicBytes:100000},delegation:{concurrency:2,maxTurns:4,graceTurns:1}}};
  const observations=new Map(),started=[],frames=[];let view={research_revision:0,state:null};
  const baseSdk=fakeSdk({});
  const sdk={...baseSdk,async createAgentSession(options){
    const id=started.find(item=>options.cwd.endsWith(createHash('sha256').update(item.action.id).digest('hex')))?.node.id;
    const observe={};observations.set(id,observe);
    return fakeSdk(observe,{block:id==='B'}).createAgentSession(options);
  }};
  const dispatch=sdkHost.createGraphNodeDispatcher(config,sdk,{getModel:()=>({id:'fake'})},{skills:[],emit:frame=>frames.push(frame),
    contextClient:{async freeze({action}){return {products:[{ref:'product-'+action.id,path:'context-results/'+action.step_id+'/report.txt',sha256:'a'.repeat(64),bytes:13,
      status:'ready',roles:['support'],owner,attempt_id:'attempt',action_id:action.id}]};}}});
  const controller=createEnterpriseGraphController({config,readResearch:async()=>structuredClone(view),
    commitResearch:async(id,request)=>{view={research_revision:view.research_revision+1,state:{...(view.state??{}),...request.changes,
      notes:[...(view.state?.notes??[]),...request.changes.notes]}};return {details:{ok:true,result:{status:'committed',receipt:{research_revision:view.research_revision}}}};},
    inspectProducts:async({products})=>({ready:true,products}),dispatchNode:async(...args)=>{started.push(args[0]);return dispatch(...args);},
    resolveInputs:async action=>({handles:[],manifests:action.input_bindings.map(binding=>JSON.parse(view.state.notes.at(-1).text).snapshot.results.find(item=>item.result_ref===binding.result_ref))})});
  const graphNode=(id,extra={})=>({id,purpose:'Inspect '+id,questions:['Question '+id],checks:['Check '+id],depends_on:[],expected_outputs:['Actual observation'],mode:'execute',execution:'delegated',instruction:'Exact '+id,source_refs:[],outputs:[{slot:'value',kind:'observation',description:'Native observation'}],inputs:[],...extra});
  try{
    assert.equal((await controller.execute('plan','plan',{goal:'Inspect actual sources',output_mode:'text',source_refs:[],nodes:[graphNode('A'),graphNode('B'),graphNode('C',{depends_on:['A'],mode:'synthesis',inputs:[{name:'prior',from:{step_id:'A',slot:'value'}}]})]})).details.ok,true);
    let state;
    for(let i=0;i<100;i++){state=await controller.readState();if(state.graph.nodes.find(item=>item.id==='A').phase==='executed')break;await new Promise(resolve=>setTimeout(resolve,2));}
    assert.deepEqual(started.map(item=>item.node.id),['A','B']);
    const proposal=await controller.readProposal(state.graph.nodes.find(item=>item.id==='A').execute_action_id);
    const receipt=proposal.receipts[0].ref;
    assert.equal((await controller.execute('record','record-A',{action_id:proposal.action.id,outcome:'completed',outputs:[{slot:'value',observation_refs:[receipt],artifact_refs:[],summary:'Observed A',scope:'Native saved output'}],limitations:[]})).details.ok,true);
    state=await controller.readState();
    assert.equal((await controller.execute('assess','assess-A',{action_id:state.graph.nodes.find(item=>item.id==='A').assess_action_id,outcome:'success',
      checks:[{description:'Check A',status:'passed',refs:[receipt],explanation:'Observed bytes'}],summary:'Accepted A'})).details.ok,true);
    for(let i=0;i<100&&!observations.get('C')?.disposed;i++)await new Promise(resolve=>setTimeout(resolve,2));
    assert.deepEqual(started.map(item=>item.node.id),['A','B','C']);
    assert.equal(observations.get('B').disposed,undefined);
    assert.ok(started.find(item=>item.node.id==='C').inputs.manifests[0].result_ref);
    await controller.close({reason:'Test complete'});
    assert.equal(observations.get('B').aborted,true);assert.equal(observations.get('B').disposed,true);
    assert.ok(frames.some(frame=>frame.type==='enterprise_graph_child_finished'&&frame.step_id==='B'&&frame.status==='cancelled'));
  }finally{await controller.close();process.chdir(previous);await rm(dir,{recursive:true,force:true});}
});
