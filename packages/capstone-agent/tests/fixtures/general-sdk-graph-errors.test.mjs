import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm,realpath,cp,symlink} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import * as host from '../../src/capstone_agent/resources/general-sdk.mjs';
import {createEnterpriseGraphController} from '../../src/capstone_agent/resources/enterprise-graph-runtime.mjs';

const sdkRoot=resolve('.grid-agent/runtime/pi/source/packages');
const sdk=await import(pathToFileURL(join(sdkRoot,'coding-agent/dist/index.js')).href);
const ai=await import(pathToFileURL(join(sdkRoot,'ai/dist/index.js')).href);
const owner={thread_id:'thread',work_id:'work',research_id:'research',goal_revision:1};
const action={id:'execute:A',step_id:'A',owner,attempt_id:'attempt',input_bindings:[],source_refs:[],source_versions:[]};
const checkpoint={ref:'checkpoint:A',revision:1};
const node={id:'A',instruction:'Inspect the supplied file or report its actual limitation.',questions:['What is available?'],expected_outputs:['Observed source or limitation']};
const config={researchTaskId:'task',researchAttemptId:'attempt',researchOwner:owner,model:'read-offline',
  extensions:[],allowedSkills:[],contextFiles:[],settings:{packages:[],extensions:[],skills:[]},
  applicationPolicy:{allowed_tools:['read']},researchRuntime:{graphSchema:'capstone-enterprise-graph/2',delegation:{maxTurns:8,graceTurns:1}}};

test('isolated organization engine cannot invoke native execution despite application grants',async()=>{
  const planner={...config,researchRuntime:{...config.researchRuntime,isolatedTaskExecution:true},
    applicationPolicy:{allowed_tools:['read','bash','write','agent_research_plan']}};
  for(const name of ['read','bash','write'])assert.equal(host.applicationToolAdmission(planner,name).accepted,false);
  assert.equal(host.applicationToolAdmission(planner,'agent_research_plan').accepted,true);
  assert.equal(host.applicationToolAdmission(planner,'agent_research_update').accepted,false);
  assert.equal(host.applicationToolAdmission(config,'read').accepted,true);
});
test('adaptive loop admits only application-granted direct tools',()=>{
  const adaptive={...config,researchRuntime:{...config.researchRuntime,isolatedTaskExecution:true,adaptiveAgentLoop:true}};
  assert.equal(host.applicationToolAdmission(adaptive,'read').accepted,true);
  assert.equal(host.applicationToolAdmission(adaptive,'bash').accepted,false);
  assert.equal(host.applicationToolAdmission(adaptive,'unregistered').accepted,false);
});
test('explicit user DR choice controls tool admission instead of model inference',()=>{
  const policy={allowed_tools:['read','agent_research_plan','agent_research_read']};
  const off={...config,applicationPolicy:policy,researchRuntime:{...config.researchRuntime,adaptiveAgentLoop:true,isolatedTaskExecution:true,deepResearch:false}};
  assert.equal(host.applicationToolAdmission(off,'read').accepted,true);
  assert.equal(host.applicationToolAdmission(off,'agent_research_plan').accepted,false);
  assert.equal(host.applicationToolAdmission(off,'agent_research_read').accepted,false);
  const on={...off,researchRuntime:{...off.researchRuntime,adaptiveAgentLoop:false,deepResearch:true}};
  assert.equal(host.applicationToolAdmission(on,'agent_research_plan').accepted,true);
  assert.equal(host.applicationToolAdmission(on,'read').accepted,false);
});
test('only an admitted Deep Research plan narrows the subsequent model tool menu',()=>{
  let hook,selected;
  host.configureAdaptiveToolHandoff({on:(name,fn)=>{assert.equal(name,'tool_result');hook=fn;},setActiveTools:names=>{selected=names;}},
    {...config,applicationPolicy:{allowed_tools:['read','agent_research_plan','agent_research_record']},
      researchRuntime:{isolatedTaskExecution:true,adaptiveAgentLoop:true}});
  hook({toolName:'read',details:{ok:true}});assert.equal(selected,undefined);
  hook({toolName:'agent_research_plan',details:{ok:false},isError:true});assert.equal(selected,undefined);
  hook({toolName:'agent_research_plan',details:{ok:true}});assert.deepEqual(selected,['agent_research_plan','agent_research_record']);
});
test('Deep Research execution roles retain granted ordinary tools',()=>{
  const child={...config,applicationPolicy:{allowed_tools:['read','write','bash']},
    researchRuntime:{adaptiveAgentLoop:true,isolatedTaskExecution:false}};
  host.configureAdaptiveToolHandoff({on:()=>assert.fail('Execution role must not install organizer handoff')},child);
  for(const name of child.applicationPolicy.allowed_tools)assert.equal(host.applicationToolAdmission(child,name).accepted,true);
  assert.equal(host.applicationToolAdmission(child,'unregistered').accepted,false);
});

test('pinned HTTP wire exports object read parameters and preserves strict graph and legacy branches',async()=>{
  const dir=await realpath(await mkdtemp(join(tmpdir(),'graph-read-wire-')));
  let controller;
  try{
    const resources=join(dir,'resources'),channel=join(dir,'channel');
    await cp(resolve('packages/capstone-agent/src/capstone_agent/resources'),resources,{recursive:true});
    const aliases=join(resources,'node_modules/@earendil-works');await mkdir(aliases,{recursive:true});
    for(const [alias,target] of [['pi-coding-agent','coding-agent'],['pi-ai','ai']])await symlink(join(sdkRoot,target),join(aliases,alias),'dir');
    for(const path of [channel,join(channel,'requests'),join(channel,'receipts')])await mkdir(path,{recursive:true});
    const [readSchema,updateSchema]=JSON.parse(execFileSync(resolve('packages/capstone-agent/.venv/bin/python'),['-c',
      'import json;from capability_agent.application.research_models import research_tool_schemas;print(json.dumps(research_tool_schemas()))'],{encoding:'utf8'}));
    const identity={run_id:'run',turn_id:'turn',attempt_id:'attempt',research_id:'research'};
    await writeFile(join(channel,'binding.json'),JSON.stringify({schema_version:'capability-research-channel/1.0',...identity,
      read_tool_schema:readSchema,update_tool_schema:updateSchema}));
    await writeFile(join(channel,'view.json'),JSON.stringify({schema_version:'capability-research-view/1.0',...identity,research_revision:0,state:null}));
    const {configureGeneralResearch}=await import(pathToFileURL(join(resources,'general-research.mjs')).href);
    let view={research_revision:0,state:null},producer,settle;
    const proposal=new Promise(resolve=>{settle=resolve;});
    controller=createEnterpriseGraphController({config:{...config,researchSources:[],researchRuntime:{...config.researchRuntime,
      graphWorkEdition:'capstone-graph-work/1',graphWork:{schema:'capstone-graph-work/1',mode:'off'},
      delegation:{concurrency:1},graphLimits:{maxNodes:8,maxItems:32,maxText:2048,maxExecutions:16,snapshotBytes:200000,publicBytes:50000}}},readResearch:async()=>structuredClone(view),
      commitResearch:async(_id,request)=>{
        assert.equal(request.expected_revision,view.research_revision);
        view={research_revision:view.research_revision+1,state:{...request.changes,notes:[...(view.state?.notes??[]),...request.changes.notes]}};
        return {details:{ok:true,result:{status:'committed',receipt:{research_revision:view.research_revision}}}};
      },inspectProducts:async({products})=>({ready:true,products}),resolveInputs:async()=>({manifests:[],handles:[]}),
      dispatchNode:async request=>{producer=request.action;return proposal;},
      readReferenceContent:async({ref})=>({ref,kind:'product',sha256:'a'.repeat(64),bytes:6,offset_bytes:0,read_bytes:6,
        next_offset_bytes:null,content_status:'text',text:'actual'})});
    assert.equal((await controller.execute('plan','plan',{goal:'Inspect saved files',output_mode:'text',source_refs:[],nodes:[{
      id:'A',purpose:'Read saved output',questions:['What was saved?'],checks:['Inspect output'],depends_on:[],expected_outputs:['Saved file'],
      mode:'execute',execution:'delegated',instruction:'Save output',source_refs:[],inputs:[],outputs:[{slot:'file',kind:'artifact',description:'Saved file'}]}]})).details.ok,true);
    settle({status:'completed',receipts:[],products:[{ref:'product-file',path:'context-results/report.csv',sha256:'a'.repeat(64),bytes:6,
      roles:['primary'],status:'ready',owner,attempt_id:'attempt',action_id:producer.id}],output:'Saved file'});
    for(let i=0;i<100;i++){
      if((await controller.readState()).graph.nodes[0].phase==='executed')break;
      await new Promise(resolve=>setImmediate(resolve));
    }
    const register=graph=>{
      const tools=[];
      configureGeneralResearch({registerTool:tool=>tools.push(tool),on:()=>{}},{...config,researchChannelPath:channel,
        researchRuntime:graph?config.researchRuntime:{}},{readReference:controller.readReference});
      return tools.find(tool=>tool.name==='agent_research_read');
    };
    const graph=register(true),legacy=register(false);
    assert.deepEqual(legacy.parameters,readSchema);
    const transport=await import(pathToFileURL(join(sdkRoot,'ai/dist/api/openai-completions.js')).href);
    const controls=[];controller.register({registerTool:tool=>controls.push(tool)});
    for(const tool of [graph,legacy,...controls.filter(tool=>['agent_research_plan','agent_research_revise','agent_research_record','agent_research_assess'].includes(tool.name))]){
      let wire,fetches=0;
      const stream=transport.streamSimple(offlineRuntime([],[]).getModel(),{systemPrompt:'Offline schema regression',
        messages:[{role:'user',content:'Inspect saved output',timestamp:0}],tools:[tool]},
      {apiKey:'offline-fixture',maxRetries:0,fetch:async(_request,init)=>{
        fetches++;wire=JSON.parse(init.body);
        return new Response(JSON.stringify({error:{message:'Offline fetch stub; no Provider request',type:'invalid_request_error'}}),
          {status:400,headers:{'content-type':'application/json'}});
      }});
      await stream.result();assert.equal(fetches,1);
      const parameters=wire.tools[0].function.parameters;
      if(['agent_research_plan','agent_research_revise'].includes(tool.name))
        assert.equal(parameters.properties.nodes.items.properties.inputs.items.oneOf.length,3);
      assert.equal(parameters.type,'object');assert.ok(parameters.properties);
      assert.equal(parameters.oneOf,undefined);assert.equal(parameters.anyOf,undefined);
      assert.deepEqual(parameters,tool.parameters);
    }
    const execute=async args=>{
      const checked=ai.validateToolArguments(graph,{type:'toolCall',id:'inspection',name:graph.name,arguments:args});
      return graph.execute('inspection',checked);
    };
    const wrongBranch=await execute({section:'overview',action_id:producer.id});
    assert.equal(wrongBranch.details.error.code,'invalid_arguments');
    assert.match(wrongBranch.content[0].text,/section.*reference/);
    assert.equal((await execute({section:'reference',action_id:producer.id})).details.ok,true);
    assert.equal((await execute({section:'reference',action_id:producer.id,ref:'product-file',mode:'text',offset_bytes:0,length_bytes:6})).details.result.text,'actual');
    for(const args of [{section:'reference'},{section:'reference',action_id:producer.id,limit:2},
      {section:'reference',action_id:producer.id,ref:'product-file',mode:'text'},
      {section:'reference',action_id:producer.id,ref:'ungranted',mode:'text',offset_bytes:0,length_bytes:6},
      {section:'overview',action_id:producer.id},{section:'notes',ref:'product-file'},{section:'receipt'}]){
      assert.equal((await execute(args)).details.ok,false,JSON.stringify(args));
    }
    for(const args of [{},{section:'overview',request_id:null},{section:'notes',offset:0,limit:1}]){
      assert.equal((await execute(args)).details.ok,true,JSON.stringify(args));
      assert.equal((await legacy.execute('legacy',args)).details.ok,true);
    }
    assert.equal((await legacy.execute('legacy',{section:'reference',action_id:producer.id})).details.ok,false);
  }finally{await controller?.close();await rm(dir,{recursive:true,force:true});}
});

function offlineRuntime(calls,observed,usage){
  const model={id:'read-offline',name:'Offline',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',
    reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
  let turn=0;
  return {getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
    streamSimple(_model,context){
      observed.splice(0,observed.length,...context.messages.filter(message=>message.role==='toolResult'));
      const call=calls[turn++];
      const message={role:'assistant',content:call?[{type:'toolCall',id:call.id,name:call.name??'read',arguments:call.args}]:[{type:'text',text:'Actual read outcome and limitation.'}],
        api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),stopReason:call?'toolUse':'stop',
        usage:usage??{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}};
      const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
    }};
}
for(const corrective of [false,true])test('pinned SDK lightweight return '+(corrective?'retains unverified findings without model repair':'accepts exact admitted references'),async()=>{
  const cwd=await realpath(await mkdtemp(join(tmpdir(),'graph-compact-return-'))),previous=process.cwd(),previousAgent=process.env.PI_CODING_AGENT_DIR;
  const calls=[],observed=[],frames=[],runtime=offlineRuntime(calls,observed),stream=runtime.streamSimple;
  let turn=0,sourceRef,manifest,validated;
  try{
    process.chdir(cwd);process.env.PI_CODING_AGENT_DIR=join(cwd,'.pi');await mkdir(process.env.PI_CODING_AGENT_DIR);
    const source=join(cwd,'source.txt'),bytes='Actual selected source';await writeFile(source,bytes);
    const digest=createHash('sha256').update(bytes).digest('hex');
    const selected={...action,definition_ref:'definition:A',execution_revision:1,source_refs:['source:raw'],
      source_versions:[{ref:'source:raw',revision:'sha256:'+digest}]};
    const declared={...node,purpose:'Read the supplied source',checks:['Read the source'],
      outputs:[{slot:'finding',kind:'observation',description:'Observed finding'}]};
    runtime.streamSimple=(model,context,...rest)=>{
      const index=turn++;
      if(index===0)calls[index]={id:'read-source',name:'read',args:{path:source}};
      else if(index===1){
        sourceRef=context.messages.find(item=>item.role==='toolResult'&&item.toolName==='read').details.native_research_source.source_ref;
        manifest={schema:'capstone-task-return/1',outputs:[{slot:'finding',summary:'Preserve these inspected facts. '.repeat(300),
          scope:'Actual selected source',observations:[corrective?'o99':sourceRef],files:[]}],
          checks:[{check:1,status:'passed',observations:[sourceRef],explanation:'Actual native read'}],limitations:[]};
        calls[index]={id:'write-return',name:'write',args:{path:'.capstone-products.json',content:JSON.stringify(manifest)}};
      }else assert.equal(index,2,'No repeated model repair loop');
      return stream(model,context,...rest);
    };
    const local={...config,applicationPolicy:{allowed_tools:['read','write','edit']},
      researchSources:['source:raw'],deliveryReviewSources:[{source_ref:'source:raw',path:source,file_name:'source.txt',sha256:digest,size_bytes:bytes.length}],
      researchRuntime:{...config.researchRuntime,lightweightTaskNodes:true}};
    const dispatch=host.createGraphNodeDispatcher(local,sdk,runtime,{skills:[],emit:event=>frames.push(event),
      contextClient:{freeze:()=>assert.fail('Observation return has no product files')}});
    const result=await dispatch({action:selected,node:declared,inputs:{manifests:[],handles:[]},checkpoint,
      contract_schema:'capstone-node-contract/1'},{validateProposal:candidate=>{validated=candidate;}});
    assert.equal(result.handoff_error,undefined,JSON.stringify(result.proposal_diagnostics));
    assert.deepEqual(result.handoff.outputs[0].observation_refs,corrective?[]:[sourceRef]);
    assert.deepEqual(result.handoff.checks[0].refs,[sourceRef]);
    assert.equal(validated.handoff.outputs[0].summary,manifest.outputs[0].summary);
    assert.equal(turn,3);
    if(corrective)assert.match(result.handoff.limitations.join('\n'),/unverified/);
    assert.equal(frames.filter(event=>event.type==='enterprise_graph_child_tool'&&event.activity==='start'&&event.tool_name==='read').length,1);
    assert.equal(frames.filter(event=>event.type==='enterprise_graph_child_tool'&&event.activity==='start'&&event.tool_name==='write').length,1);
    const child=join(cwd,'.research-workers',createHash('sha256').update(selected.id).digest('hex'));
    assert.equal(JSON.parse(await readFile(join(child,'.capstone-products.json'),'utf8')).outputs[0].summary,manifest.outputs[0].summary);
  }finally{process.chdir(previous);if(previousAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=previousAgent;await rm(cwd,{recursive:true,force:true});}
});
test('pinned SDK inner tool loop stops an identical rejected selection but allows a distinct correction',async()=>{
  for(const corrected of [false,true]){
    const cwd=await realpath(await mkdtemp(join(tmpdir(),'graph-inner-reject-'))),previous=process.cwd(),previousAgent=process.env.PI_CODING_AGENT_DIR;
    let requests=0,progress='unchanged',guard;const errors=[],events=[];
    try{
      process.chdir(cwd);process.env.PI_CODING_AGENT_DIR=join(cwd,'.pi');await mkdir(process.env.PI_CODING_AGENT_DIR);
      const controller={readParentInputs:async()=>null,progressKey:async()=>progress};
      const calls=[{id:'new-call-one',name:'agent_research_inspect',args:{path:'missing.txt'}},
        {id:'new-call-two',name:'agent_research_inspect',args:{path:corrected?'actual.txt':'missing.txt'}}];
      const modelRuntime=offlineRuntime(calls,[],{input:2,output:3,cacheRead:0,cacheWrite:0,totalTokens:5,cost:{total:0}}),stream=modelRuntime.streamSimple;
      modelRuntime.streamSimple=(...args)=>{requests++;return stream(...args);};
      const settingsManager=sdk.SettingsManager.inMemory(config.settings),loader=new sdk.DefaultResourceLoader({cwd,agentDir:process.env.PI_CODING_AGENT_DIR,
        settingsManager,noExtensions:true,noSkills:true,noPromptTemplates:true,noThemes:true,noContextFiles:true,agentsFilesOverride:()=>({agentsFiles:[]}),extensionFactories:[pi=>{
          guard=host.configureGraphParentContext(pi,config,controller);
          pi.registerTool({name:'agent_research_inspect',description:'Offline exact selection',parameters:{type:'object',additionalProperties:false,properties:{path:{type:'string'}},required:['path']},
            execute:async(id,args)=>{
              if(args.path==='actual.txt'){progress='actual-accepted-output';return {content:[{type:'text',text:'Saved actual output'}],details:{ok:true}};}
              return {isError:true,content:[{type:'text',text:'Confirmed selection rejection'}],details:{ok:false,error:{category:'rejected',code:'graph_context_rejected',request_id:'ctx-'+id}}};
            }});
        }]});await loader.reload();
      const {session}=await sdk.createAgentSession({cwd,agentDir:process.env.PI_CODING_AGENT_DIR,modelRuntime,model:modelRuntime.getModel(),
        resourceLoader:loader,settingsManager,sessionManager:sdk.SessionManager.inMemory()});
      try{
        await session.bindExtensions({onError:event=>errors.push(event.message)});session.setActiveToolsByName(['agent_research_inspect']);
        const run=host.runSettledPrompt(session,{kind:'text',text:'Inspect exact output.'},null,event=>events.push(event),undefined,{failure:()=>guard?.failure()});
        if(corrected)await run;else await assert.rejects(run,error=>error.code==='continuation_no_progress');
        assert.equal(requests,corrected?3:2,JSON.stringify({errors,results:session.messages.filter(item=>item.role==='toolResult').map(item=>({error:item.isError,details:item.details}))}));
        if(corrected)assert.equal(session.messages.at(-1).stopReason,'stop');
        else{
          assert.match(session.messages.at(-1).errorMessage,/Repeated rejected graph selection/);
          const end=events.find(item=>item.type==='agent_end');assert.equal(end.success,false);assert.equal(end.code,'continuation_no_progress');
          assert.equal(end.messages.length,2);assert.equal(end.messages.reduce((n,item)=>n+item.usage.totalTokens,0),10);
          assert.ok(end.messages.every(item=>item.errorCode===undefined));
        }
      }finally{session.dispose();}
    }finally{process.chdir(previous);if(previousAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=previousAgent;await rm(cwd,{recursive:true,force:true});}
  }
});
test('parent private context uses the exact input map and ignores unrelated checkpoint advance',async()=>{
  const handlers=new Map(),selected={action:{...action,id:'parent:P',input_bindings:[{name:'prior',result_ref:'result:v1'}]},
    inputs:{manifests:[{result_ref:'result:v1',artifact_refs:['artifact:v1']}],handles:[{ref:'artifact:v1',result_ref:'result:v1',
      path:'/exact/retained-file.csv',immutable:true,read_only:true}]}};
  const controller={readParentInputs:async()=>structuredClone(selected)};
  host.configureGraphParentContext({on:(name,fn)=>handlers.set(name,fn)},config,controller);
  const result=await handlers.get('context')({messages:[{role:'custom',customType:'capstone-research-state',content:'Existing public state'}]},{});
  assert.equal(result.messages.length,2);const custom=result.messages.at(-1);
  assert.equal(custom.display,false);assert.match(custom.content,/absolute FILE path/);assert.match(custom.content,/prior/);
  assert.match(custom.content,/\/exact\/retained-file.csv/);
  // Sibling checkpoints do not change the frozen parent action or selected inputs.
  controller.research_revision=99;
  await handlers.get('before_model_request')({context:{messages:result.messages.map(item=>({role:'user',content:item.content}))}},{});
  const next=await handlers.get('context')({messages:result.messages},{});
  assert.equal(next.messages.filter(item=>item.customType==='capstone-graph-parent-inputs').length,1);
  await assert.rejects(handlers.get('before_model_request')({context:{messages:[...next.messages.map(item=>({role:'user',content:item.content})),
    {role:'user',content:'Granted inputs for parent execute action foreign'}]}},{}),/Parent input context/);
  await handlers.get('context')({messages:result.messages},{});
  selected.action.id='parent:new-version';
  await assert.rejects(handlers.get('before_model_request')({context:{messages:next.messages.map(item=>({role:'user',content:item.content}))}},{}),/Parent input context/);
});
test('graph summary and parent map keep independent safe history anchors',async()=>{
  const handlers=new Map(),selected={action:{...action,id:'parent:stable'},inputs:{manifests:[],handles:[]}};
  const controller={readParentInputs:async()=>selected.action?structuredClone(selected):null};
  host.configureGraphParentContext({on:(name,fn)=>handlers.set(name,fn)},config,controller);
  let summary='fresh-summary-v1';
  const transform=async history=>(await handlers.get('context')({messages:[...history,{role:'custom',customType:'capstone-research-state',content:summary,display:false,timestamp:0}]},{})).messages;
  const history=[{role:'user',content:'Original task',timestamp:1},{role:'assistant',content:[{type:'toolCall',id:'call-one',name:'probe'},{type:'toolCall',id:'call-two',name:'probe'}],timestamp:2},
    {role:'toolResult',toolCallId:'call-one',toolName:'probe',content:[],timestamp:3},{role:'toolResult',toolCallId:'call-two',toolName:'probe',content:[],timestamp:4}];
  const first=await transform(history),nextHistory=[...history,{role:'assistant',content:[{type:'text',text:'Next actual response'}],timestamp:5}],next=await transform(nextHistory);
  assert.deepEqual(next.slice(0,first.length),first);assert.equal(next.filter(item=>item.customType==='capstone-research-state').length,1);
  assert.equal(next.filter(item=>item.customType==='capstone-graph-parent-inputs').length,1);assert.equal(history.length,4);
  summary='fresh-summary-v2';const changed=await transform(nextHistory);
  assert.equal(changed[4].customType,'capstone-graph-parent-inputs');assert.equal(changed.at(-1).content,summary);
  const cropped=await transform([nextHistory.at(-1)]);assert.equal(cropped[1].customType,'capstone-research-state');assert.equal(cropped[2].customType,'capstone-graph-parent-inputs');
  const duplicate=[...history,{role:'assistant',content:[{type:'toolCall',id:'call-two',name:'probe'}],timestamp:6},
    {role:'toolResult',toolCallId:'call-two',toolName:'probe',content:[],timestamp:7}];
  const rebuilt=await transform(duplicate);assert.deepEqual(rebuilt.slice(0,duplicate.length),duplicate);
  assert.deepEqual(rebuilt.slice(-2).map(item=>item.customType),['capstone-research-state','capstone-graph-parent-inputs']);
  for(const event of ['session_compact','session_compact_failed','session_start','session_tree']){
    handlers.get('session_before_compact')();
    await assert.rejects(transform(nextHistory),/Parent input context/);
    // The SDK's own compactor bypasses context and uses this same request hook.
    await handlers.get('before_model_request')({context:{messages:[]}},{signal:new AbortController().signal});
    handlers.get(event)();const reset=await transform(nextHistory);
    assert.deepEqual(reset.slice(0,nextHistory.length),nextHistory);assert.equal(reset.at(-1).customType,'capstone-graph-parent-inputs');
  }
  selected.action={...action,id:'parent:new'};const replacement=await transform(nextHistory);assert.match(replacement.at(-1).content,/parent:new/);
  selected.action=null;const absent=await transform(nextHistory);assert.equal(absent.some(item=>item.customType==='capstone-graph-parent-inputs'),false);
  const legacy=[];assert.equal(host.configureGraphParentContext({on:name=>legacy.push(name)},{...config,researchRuntime:{}},controller),undefined);assert.deepEqual(legacy,[]);
});
test('pinned HTTP wire retains both graph context packets before appended tool history',async()=>{
  const cwd=await realpath(await mkdtemp(join(tmpdir(),'graph-context-wire-'))),previousAgent=process.env.PI_CODING_AGENT_DIR;
  let session;
  try{
    process.env.PI_CODING_AGENT_DIR=join(cwd,'.pi');await mkdir(process.env.PI_CODING_AGENT_DIR);
    const resources=join(cwd,'resources'),channel=join(cwd,'channel');
    await cp(resolve('packages/capstone-agent/src/capstone_agent/resources'),resources,{recursive:true});
    const aliases=join(resources,'node_modules/@earendil-works');await mkdir(aliases,{recursive:true});
    for(const [alias,target] of [['pi-coding-agent','coding-agent'],['pi-ai','ai']])await symlink(join(sdkRoot,target),join(aliases,alias),'dir');
    for(const path of [channel,join(channel,'requests'),join(channel,'receipts')])await mkdir(path,{recursive:true});
    const [readSchema,updateSchema]=JSON.parse(execFileSync(resolve('packages/capstone-agent/.venv/bin/python'),['-c',
      'import json;from capability_agent.application.research_models import research_tool_schemas;print(json.dumps(research_tool_schemas()))'],{encoding:'utf8'}));
    const identity={run_id:'run',turn_id:'turn',attempt_id:'attempt',research_id:'research'};
    await writeFile(join(channel,'binding.json'),JSON.stringify({schema_version:'capability-research-channel/1.0',...identity,read_tool_schema:readSchema,update_tool_schema:updateSchema}));
    await writeFile(join(channel,'view.json'),JSON.stringify({schema_version:'capability-research-view/1.0',...identity,research_revision:1,
      state:{research_id:'research',revision:1,goal:'Inspect retained inputs',condition_refs:[],claims:[],notes:[],open_questions:[]}}));
    const {configureGeneralResearch}=await import(pathToFileURL(join(resources,'general-research.mjs')).href);
    const transport=await import(pathToFileURL(join(sdkRoot,'ai/dist/api/openai-completions.js')).href),wires=[];
    let rejectCompaction=false;
    const modelRuntime=offlineRuntime([],[]),model=modelRuntime.getModel();
    modelRuntime.streamSimple=(_model,context,options)=>transport.streamSimple(model,context,{...options,apiKey:'offline-fixture',maxRetries:0,
      fetch:async(_request,init)=>{
        wires.push(JSON.parse(init.body));const turn=wires.length;
        if(rejectCompaction)return new Response(JSON.stringify({error:{message:'Offline compaction failure',type:'invalid_request_error'}}),
          {status:400,headers:{'content-type':'application/json'}});
        const names=turn===1?['one','two']:turn===2?['three']:[];
        const delta=names.length?{role:'assistant',tool_calls:names.map((id,index)=>({index,id,type:'function',function:{name:'probe',arguments:'{}'}}))}:
          {role:'assistant',content:'Actual bounded completion.'};
        const chunk={id:'offline-'+turn,object:'chat.completion.chunk',created:0,model:model.id,
          choices:[{index:0,delta,finish_reason:names.length?'tool_calls':'stop'}]};
        return new Response('data: '+JSON.stringify(chunk)+'\n\ndata: [DONE]\n\n',{headers:{'content-type':'text/event-stream'}});
      }});
    const settingsManager=sdk.SettingsManager.inMemory({...config.settings,compaction:{enabled:false,keepRecentTokens:1}}),loader=new sdk.DefaultResourceLoader({cwd,agentDir:process.env.PI_CODING_AGENT_DIR,
      settingsManager,noExtensions:true,noSkills:true,noPromptTemplates:true,noThemes:true,noContextFiles:true,agentsFilesOverride:()=>({agentsFiles:[]}),extensionFactories:[pi=>{
        configureGeneralResearch(pi,{...config,researchChannelPath:channel},{getControllerState:()=>({graph:{schema:'capstone-enterprise-graph/2'}})});
        host.configureGraphParentContext(pi,config,{readParentInputs:async()=>({action,inputs:{manifests:[],handles:[]}})});
        pi.registerTool({name:'probe',description:'Return a bounded result',parameters:{type:'object',properties:{},additionalProperties:false},
          execute:async()=>({content:[{type:'text',text:'Actual tool result'}],details:{ok:true}})});
      }]});await loader.reload();
    ({session}=await sdk.createAgentSession({cwd,agentDir:process.env.PI_CODING_AGENT_DIR,modelRuntime,model,resourceLoader:loader,settingsManager,sessionManager:sdk.SessionManager.inMemory()}));
    const errors=[];await session.bindExtensions({onError:event=>errors.push(event.message)});session.setActiveToolsByName(['probe']);
    await session.prompt('Use retained inputs.');assert.deepEqual(errors,[]);assert.equal(wires.length,3);
    for(let index=1;index<wires.length;index++)assert.deepEqual(wires[index].messages.slice(0,wires[index-1].messages.length),wires[index-1].messages);
    for(const wire of wires){
      const text=wire.messages.map(item=>typeof item.content==='string'?item.content:JSON.stringify(item.content));
      assert.equal(text.filter(item=>item.includes('Granted inputs for parent execute action')).length,1);
      assert.equal(text.filter(item=>item.includes('Inspect retained inputs')).length,1);
    }
    const calls=wires[1].messages.findIndex(item=>item.tool_calls?.length===2);
    assert.deepEqual(wires[1].messages.slice(calls+1,calls+3).map(item=>item.tool_call_id),['one','two']);
    assert.equal(session.messages.some(item=>item.role==='custom'),false);
    await session.compact('Keep exact input references.');assert.equal(wires.length,4);assert.deepEqual(errors,[]);
    await session.prompt('Continue with retained inputs.');assert.equal(wires.length,5);assert.deepEqual(errors,[]);
    assert.equal(wires.at(-1).messages.filter(item=>JSON.stringify(item.content).includes('Granted inputs for parent execute action')).length,1);
    rejectCompaction=true;await assert.rejects(session.compact('Keep exact input references.'),/Offline compaction failure/);
    rejectCompaction=false;await session.prompt('Continue after failed compaction.');assert.equal(wires.length,7);assert.deepEqual(errors,[]);
    assert.equal(wires.at(-1).messages.filter(item=>JSON.stringify(item.content).includes('Granted inputs for parent execute action')).length,1);
  }finally{session?.dispose();if(previousAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=previousAgent;await rm(cwd,{recursive:true,force:true});}
});
test('an accepted sibling settlement clears an old repeated-rejection guard before the next request',async()=>{
  const handlers=new Map();let progress='before';
  host.configureGraphParentContext({on:(name,fn)=>handlers.set(name,fn)},config,{readParentInputs:async()=>null,progressKey:async()=>progress});
  const failure={toolName:'agent_research_inspect',input:{action_id:'exact',products:[{path:'missing.txt',role:'primary'}]},details:{ok:false,error:{category:'rejected',code:'graph_context_rejected'}}};
  await handlers.get('tool_result')(failure,{});await handlers.get('tool_result')(failure,{});
  progress='accepted-sibling-output';await handlers.get('context')({messages:[]},{});
  await handlers.get('before_model_request')({context:{messages:[]}},{});
});
test('parent private guard rejects swallowed context failures and emits no foreign map without a parent',async()=>{
  const handlers=new Map();let selected=null;
  const controller={readParentInputs:async()=>{if(selected instanceof Error)throw selected;return selected;}};
  host.configureGraphParentContext({on:(name,fn)=>handlers.set(name,fn)},config,controller);
  const empty=await handlers.get('context')({messages:[]},{});assert.deepEqual(empty.messages,[]);
  await handlers.get('before_model_request')({context:{messages:[]}},{});
  selected=Error('Simulated context failure');
  await assert.rejects(handlers.get('context')({messages:[]},{}),/Simulated/);
  await assert.rejects(handlers.get('before_model_request')({context:{messages:[]}},{}),/Parent input context/);
});
test('pinned SDK blocks a swallowed invalid parent-map hook before any model response',async()=>{
  const cwd=await realpath(await mkdtemp(join(tmpdir(),'graph-parent-hook-'))),previous=process.cwd(),previousAgent=process.env.PI_CODING_AGENT_DIR;
  let requests=0;const errors=[];
  try{
    process.chdir(cwd);process.env.PI_CODING_AGENT_DIR=join(cwd,'.pi');await mkdir(process.env.PI_CODING_AGENT_DIR);
    const modelRuntime=offlineRuntime([],[]),stream=modelRuntime.streamSimple;
    modelRuntime.streamSimple=(...args)=>{requests++;return stream(...args);};
    const controller={readParentInputs:async()=>({action,inputs:{manifests:[{result_ref:'result:v1'}],
      handles:[{ref:'artifact:v1',result_ref:'result:v1',path:'relative-file',immutable:true,read_only:true}]}})};
    const settingsManager=sdk.SettingsManager.inMemory(config.settings),loader=new sdk.DefaultResourceLoader({cwd,agentDir:process.env.PI_CODING_AGENT_DIR,
      settingsManager,noExtensions:true,noSkills:true,noPromptTemplates:true,noThemes:true,noContextFiles:true,agentsFilesOverride:()=>({agentsFiles:[]}),
      extensionFactories:[pi=>host.configureGraphParentContext(pi,config,controller)]});await loader.reload();
    const {session}=await sdk.createAgentSession({cwd,agentDir:process.env.PI_CODING_AGENT_DIR,modelRuntime,model:modelRuntime.getModel(),
      resourceLoader:loader,settingsManager,sessionManager:sdk.SessionManager.inMemory()});
    try{
      await session.bindExtensions({onError:event=>errors.push(event)});await session.prompt('Read selected inputs.');
      assert.equal(requests,0);assert.ok(errors.length>0);assert.match(session.messages.at(-1).errorMessage,/Parent input context/);
    }finally{session.dispose();}
  }finally{process.chdir(previous);if(previousAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=previousAgent;await rm(cwd,{recursive:true,force:true});}
});
test('graph adapter rejects invalid file handles before child launch',async()=>{
  for(const patch of [{path:undefined},{path:'relative/result'},{path:42},{ref:'/private/ref'},{immutable:false},{read_only:false}]){
    let launched=false;
    const dispatch=host.createGraphNodeDispatcher(config,{createAgentSession:()=>{launched=true;throw Error('Child launched');}},
      offlineRuntime([],[]),{skills:[],emit:()=>{}});
    const handle={ref:'obs:v1',result_ref:'result:v1',path:'/exact/file',immutable:true,read_only:true,...patch};
    await assert.rejects(dispatch({action,node,checkpoint,inputs:{manifests:[{result_ref:'result:v1'}],handles:[handle]}}),
      error=>error.code==='graph_input_contract'&&/handle\[0\].*(path|ref|immutable|read_only)/.test(error.message));
    assert.equal(launched,false);
  }
});
test('pinned SDK model context contains selected raw source only and exact retained result handles',async()=>{
  const cwd=await realpath(await mkdtemp(join(tmpdir(),'graph-real-scope-'))),previous=process.cwd(),previousAgent=process.env.PI_CODING_AGENT_DIR;
  const seen=[],contexts=[],runtime=offlineRuntime([],seen),stream=runtime.streamSimple;
  runtime.streamSimple=(model,context,...args)=>{contexts.push(JSON.stringify(context));return stream(model,context,...args);};
  const alpha={source_ref:'raw-A',path:join(cwd,'alpha.txt'),file_name:'alpha.txt',sha256:'a'.repeat(64),size_bytes:5};
  const beta={...alpha,source_ref:'raw-B',path:join(cwd,'beta.txt'),file_name:'beta.txt',sha256:'b'.repeat(64)};
  try{
    process.chdir(cwd);process.env.PI_CODING_AGENT_DIR=join(cwd,'.pi');
    for(const [id,refs] of [['A',['raw-A']],['C',[]]]){
      const local={...config,runtimeEnvironment:'VERIFIED OFFLINE LIBRARIES AND CHINESE FONT',
        contextFiles:[{path:'ambient',content:'AMBIENT GLOBAL SOURCE CATALOG'}],deliveryReviewSources:[alpha,beta],researchSources:['raw-A','raw-B']};
      const selected={...action,id:'execute:'+id,step_id:id,input_bindings:[{name:'prior',result_ref:'result:v1'}],source_refs:refs,source_versions:refs.map(ref=>({ref,revision:'sha256:'+alpha.sha256}))};
      const dispatch=host.createGraphNodeDispatcher(local,sdk,runtime,{skills:[],emit:()=>{},contextClient:{freeze:()=>assert.fail('No products')}});
      const inputs={manifests:[{result_ref:'result:v1',artifact_refs:['artifact:v1']}],handles:[{ref:'artifact:v1',result_ref:'result:v1',path:'/sealed/exact-v1',immutable:true,read_only:true}]};
      const result=await dispatch({action:selected,node:{...node,id,source_refs:refs},inputs,checkpoint},{});
      assert.equal(result.status,'completed',JSON.stringify({output:result.output,receipts:result.receipts}));
      const context=contexts.at(-1);
      assert.ok(!context.includes('beta.txt'));assert.ok(!context.includes('AMBIENT GLOBAL SOURCE CATALOG'));
      assert.match(context,/VERIFIED OFFLINE LIBRARIES AND CHINESE FONT/);
      assert.equal(context.includes('alpha.txt'),id==='A');assert.ok(context.includes('/sealed/exact-v1'));
      assert.ok(context.includes('host-bound node instruction'));assert.ok(context.includes('precise missing input'));
      assert.match(context,/absolute FILE path/);assert.match(context,/handle.path unchanged/);
      assert.match(context,/Do not prepend cwd/);assert.match(context,/input_names/);assert.match(context,/product/);
      assert.match(context,/read.*\\"path\\":\\"\/sealed\/exact-v1/);
      const policy=JSON.parse(context).systemPrompt;
      assert.ok(policy.includes(JSON.stringify({schema:'capstone-workspace-products/1',products:[{path:'actual-relative-file',role:'primary'}]})));
      assert.match(policy,/primary.*requested deliverable/);assert.match(policy,/support.*supporting material/);
      assert.match(policy,/reproduction.*reproduce/);assert.match(policy,/only files you actually wrote/);
      assert.match(policy,/host computes.*hashes and sizes/i);assert.match(policy,/Do not rehash/);
      assert.match(policy,/declared necessary checks.*numerical checks/);assert.match(policy,/questions are met.*return.*findings.*paths.*limitations/);
      assert.match(policy,/Do not scan sibling.*context directories/);assert.match(policy,/precise missing input.*parent.*revise/);
    }
  }finally{process.chdir(previous);if(previousAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=previousAgent;await rm(cwd,{recursive:true,force:true});}
});

for(const corrective of [false,true])test('pinned SDK child retains thrown read failure'+(corrective?' then valid correction':''),async()=>{
  const cwd=await realpath(await mkdtemp(join(tmpdir(),'graph-errors-'))),previous=process.cwd(),previousAgent=process.env.PI_CODING_AGENT_DIR;
  const frames=[],observed=[];
  try{
    process.chdir(cwd);process.env.PI_CODING_AGENT_DIR=join(cwd,'agent');await mkdir(process.env.PI_CODING_AGENT_DIR);
    const valid=join(cwd,'valid.txt');await writeFile(valid,'Actual inspected bytes');
    const calls=[{id:'missing-file',args:{path:join(cwd,'missing.txt')}}];
    if(corrective)calls.push({id:'valid-file',args:{path:valid}});
    const dispatch=host.createGraphNodeDispatcher(config,sdk,offlineRuntime(calls,observed),{skills:[],emit:event=>frames.push(event),
      contextClient:{freeze:async()=>assert.fail('Read-only child has no product selection')}});
    const result=await dispatch({action,node,inputs:{manifests:[],handles:[]},checkpoint});
    assert.equal(observed[0].isError,true);assert.match(observed[0].content[0].text,/ENOENT/);
    assert.equal(result.status,corrective?'completed':'failed');
    assert.equal(result.receipts.length,corrective?2:1);
    const receipt=result.receipts[0];assert.equal(receipt.status,'failed');assert.equal(receipt.action_id,action.id);
    const end=frames.find(event=>event.type==='enterprise_graph_child_tool'&&event.activity==='end');
    assert.equal(end.is_error,true);assert.match(end.result.content[0].text,/ENOENT/);
    assert.equal(receipt.ref,'execution-receipt:'+createHash('sha256').update('task\0'+end.tool_call_id).digest('hex'));
    assert.equal(end.result.details?.native_research_source,undefined);
    if(corrective){assert.equal(observed[1].isError,false);assert.equal(result.receipts[1].status,'completed');}
  }finally{process.chdir(previous);if(previousAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=previousAgent;await rm(cwd,{recursive:true,force:true});}
});

test('parent cancellation before admission does not acquire a graph action',async()=>{
  const abort=new AbortController();abort.abort();let began=0;
  const controller={beginTool:async()=>{began++;throw new Error('Must not acquire');}};
  const tool=host.applicationToolOptions({...config,researchChannelPath:'private'},[{name:'read',execute:async()=>assert.fail('unexecuted')}],()=>controller).customTools[0];
  await assert.rejects(tool.execute('cancelled-before-admission',{},abort.signal),error=>error.name==='AbortError');
  assert.equal(began,0);
});

test('parent wrapper rethrows pinned SDK missing-file and invalid-offset reads with exact failure bindings',async()=>{
  const cwd=await realpath(await mkdtemp(join(tmpdir(),'graph-parent-errors-'))),frames=[],ended=[];
  const original=process.stdout.write;process.stdout.write=chunk=>{frames.push(JSON.parse(chunk));return true;};
  try{
    await writeFile(join(cwd,'valid.txt'),'One actual line');
    const controller={beginTool:async({toolCallId,toolName})=>({action,checkpoint,toolCallId,toolName}),
      endTool:(token,result,error)=>ended.push({token,result,error}),completeTool:async()=>assert.fail('Thrown reads cannot complete')};
    const tool=host.applicationToolOptions({...config,researchChannelPath:'private'},host.createIsolatedNativeTools(sdk,cwd),()=>controller).customTools.find(tool=>tool.name==='read');
    await assert.rejects(tool.execute('missing-file',{path:'missing.txt'}),/ENOENT/);
    await assert.rejects(tool.execute('invalid-offset',{path:'valid.txt',offset:1000}),/offset|beyond|lines/i);
    assert.equal(ended.length,2);
    assert.ok(ended.every(item=>item.result===undefined&&item.error instanceof Error&&item.token.action===action));
    assert.deepEqual(frames.map(event=>event.type),['enterprise_graph_tool_binding','enterprise_graph_tool_failure','enterprise_graph_tool_binding','enterprise_graph_tool_failure']);
    for(const event of frames){assert.equal(event.action_id,action.id);assert.deepEqual(event.checkpoint,checkpoint);}
    assert.deepEqual(frames.filter(event=>event.status).map(event=>event.status),['failed','failed']);
  }finally{process.stdout.write=original;await rm(cwd,{recursive:true,force:true});}
});

test('pinned SDK argument validation records the rejected call without a fabricated execution start',async()=>{
  const cwd=await realpath(await mkdtemp(join(tmpdir(),'graph-args-'))),previous=process.cwd(),previousAgent=process.env.PI_CODING_AGENT_DIR;
  const frames=[],observed=[];
  try{
    process.chdir(cwd);process.env.PI_CODING_AGENT_DIR=join(cwd,'agent');await mkdir(process.env.PI_CODING_AGENT_DIR);
    const dispatch=host.createGraphNodeDispatcher(config,sdk,offlineRuntime([{id:'bad-args',args:{}}],observed),{skills:[],emit:event=>frames.push(event)});
    const result=await dispatch({action,node,inputs:{manifests:[],handles:[]},checkpoint});
    assert.equal(observed[0].isError,true);
    assert.equal(result.receipts.length,1);assert.equal(result.receipts[0].status,'failed');
    assert.ok(frames.some(event=>event.type==='enterprise_graph_tool_binding'));
    assert.ok(!frames.some(event=>event.type==='enterprise_graph_child_tool'&&event.activity==='start'));
    const end=frames.find(event=>event.type==='enterprise_graph_child_tool'&&event.activity==='end');
    assert.equal(end.is_error,true);assert.equal(end.execution_ms,undefined);
  }finally{process.chdir(previous);if(previousAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=previousAgent;await rm(cwd,{recursive:true,force:true});}
});

test('pinned SDK in-flight read abort drains owned child and retains cancelled call receipt',async()=>{
  const cwd=await realpath(await mkdtemp(join(tmpdir(),'graph-abort-'))),previous=process.cwd(),previousAgent=process.env.PI_CODING_AGENT_DIR;
  const frames=[],observed=[],abort=new AbortController();
  let started,release;
  const entered=new Promise(resolve=>{started=resolve;}),blocked=new Promise(resolve=>{release=resolve;});
  const wrappedSdk={...sdk,createCodingTools:cwd=>[sdk.createReadTool(cwd,{operations:{
    access:async()=>{},readFile:async()=>{started();await blocked;return Buffer.from('Late bytes');}}})]};
  let job;
  try{
    process.chdir(cwd);process.env.PI_CODING_AGENT_DIR=join(cwd,'agent');await mkdir(process.env.PI_CODING_AGENT_DIR);
    const dispatch=host.createGraphNodeDispatcher(config,wrappedSdk,offlineRuntime([{id:'aborted-read',args:{path:'slow.txt'}}],observed),{skills:[],emit:event=>frames.push(event)});
    job=dispatch({action,node,inputs:{manifests:[],handles:[]},checkpoint},{signal:abort.signal});
    await entered;abort.abort();
    const result=await job;
    assert.equal(result.status,'cancelled');assert.equal(result.receipts.length,1);
    assert.equal(result.receipts[0].status,'cancelled');assert.equal(result.receipts[0].action_id,action.id);
    const failure=frames.find(event=>event.type==='enterprise_graph_tool_failure');
    assert.equal(failure.status,'cancelled');assert.deepEqual(failure.checkpoint,checkpoint);
    assert.equal(failure.tool_call_id,result.receipts[0].tool_call_id);
    const end=frames.find(event=>event.type==='enterprise_graph_child_tool'&&event.activity==='end');
    assert.equal(end.is_error,true);assert.equal(end.result.content[0].text,'Operation aborted');
    assert.equal(frames.at(-1).type,'enterprise_graph_child_finished');assert.equal(frames.at(-1).status,'cancelled');
  }finally{abort.abort();release();await job;process.chdir(previous);if(previousAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=previousAgent;await rm(cwd,{recursive:true,force:true});}
});
