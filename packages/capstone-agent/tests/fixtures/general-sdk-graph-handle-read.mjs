// Test-only seam: real Python context grant -> child prompt -> pinned SDK read.
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,rm,realpath,cp,symlink,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createGraphNodeDispatcher,configureGraphParentContext,applicationToolOptions,createIsolatedNativeTools} from '../../src/capstone_agent/resources/general-sdk.mjs';
import {createEnterpriseGraphController} from '../../src/capstone_agent/resources/enterprise-graph-runtime.mjs';

const sdkRoot=resolve('.grid-agent/runtime/pi/source/packages');
const sdk=await import(pathToFileURL(join(sdkRoot,'coding-agent/dist/index.js')).href);
const ai=await import(pathToFileURL(join(sdkRoot,'ai/dist/index.js')).href);
let input='';for await(const chunk of process.stdin)input+=chunk;
const {action,inputs,checkpoint,expected,kind,parent,inspection}=JSON.parse(input);
const model={id:'grant-read',name:'Offline',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',
  reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
let turns=0,readPath,parentActionId;
const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
  streamSimple(_model,context){
    let content,stopReason;
    if(turns++===0){
      const prompt=context.messages.filter(item=>item.role==='user').flatMap(item=>typeof item.content==='string'?[item.content]:
        item.content.filter(part=>part.type==='text').map(part=>part.text)).find(text=>text.includes('Exact host-selected immutable input manifests and file map'));
      const line=prompt.split('\n').find(item=>item.startsWith('Exact host-selected immutable input manifests and file map'));
      assert.ok(line,'Model needs the exact file map');
      const mapped=JSON.parse(line.slice(line.indexOf('): ')+3));
      assert.deepEqual(mapped.manifests,inputs.manifests);
      const handle=mapped.handles.find(item=>item.kind===kind);
      assert.ok(handle);assert.deepEqual(handle.input_names,['prior']);
      for(const [key,value] of Object.entries(inputs.handles[0]))assert.deepEqual(handle[key],value);
      readPath=handle.path;content=[parent?{type:'toolCall',id:'inspect-granted',name:'agent_research_read',arguments:{section:'reference',action_id:parentActionId,
        ref:handle.ref,mode:'text',offset_bytes:0,length_bytes:Buffer.byteLength(expected)}}:
        {type:'toolCall',id:'read-granted',name:'read',arguments:{path:handle.path}}];stopReason='toolUse';
    }else if(parent&&turns===2){
      const result=context.messages.filter(item=>item.role==='toolResult').at(-1);
      assert.equal(result.isError,false);assert.equal(result.details.result.text,expected);
      assert.equal(result.details.result.inspection_only,true);assert.equal(result.details.native_research_source,undefined);
      content=[{type:'toolCall',id:'read-granted',name:'read',arguments:{path:readPath}}];stopReason='toolUse';
    }else{
      const result=context.messages.filter(item=>item.role==='toolResult').at(-1);
      assert.equal(result.isError,false);assert.equal(result.content[0].text,expected);
      content=[{type:'text',text:'Read exact granted bytes.'}];stopReason='stop';
    }
    const message={role:'assistant',content,stopReason,api:model.api,provider:model.provider,model:model.id,timestamp:0,
      usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}};
    const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:stopReason,message});stream.end();return stream;
  }};
const cwd=await realpath(await mkdtemp(join(tmpdir(),'graph-grant-read-'))),prior=process.cwd();
try{
  process.chdir(cwd);process.env.PI_CODING_AGENT_DIR=join(cwd,'.pi');await mkdir(process.env.PI_CODING_AGENT_DIR);
  const config={researchTaskId:'grant-read',researchOwner:action.owner,researchAttemptId:action.attempt_id,model:model.id,
    extensions:[],allowedSkills:[],contextFiles:[],settings:{packages:[],extensions:[],skills:[]},applicationPolicy:{allowed_tools:['read']},
    researchRuntime:{graphSchema:'capstone-enterprise-graph/2',delegation:{maxTurns:4,graceTurns:1}}};
  if(parent){
    config.researchChannelPath='private-fixture';config.researchResults=inputs.manifests;
    config.researchRuntime={...config.researchRuntime,graphLimits:{maxNodes:8,maxItems:32,maxText:4096,maxExecutions:16,snapshotBytes:200000,publicBytes:50000},
      delegation:{...config.researchRuntime.delegation,concurrency:1}};
    let view={research_revision:0,state:null},resolutions=0;
    const controller=createEnterpriseGraphController({config,readResearch:async()=>structuredClone(view),
      commitResearch:async(_id,request)=>{assert.equal(request.expected_revision,view.research_revision);
        view={research_revision:view.research_revision+1,state:{...request.changes,notes:[...(view.state?.notes??[]),...request.changes.notes]}};
        return {details:{ok:true,result:{status:'committed',receipt:{research_revision:view.research_revision}}}};},
      inspectProducts:()=>assert.fail('No new products'),dispatchNode:()=>assert.fail('Parent execution only'),onProgress:()=>{},
      readReferenceContent:async({ref,offset_bytes,length_bytes})=>{assert.equal(ref,inspection.ref);assert.equal(offset_bytes,0);
        assert.equal(length_bytes,Buffer.byteLength(expected));return inspection;},
      resolveInputs:async selected=>{resolutions++;assert.deepEqual(selected.source_refs,[]);
        assert.deepEqual(selected.input_bindings.map(item=>item.result_ref),inputs.manifests.map(item=>item.result_ref));return inputs;}});
    const node={id:'P',purpose:'Read exact retained content',questions:['What was saved?'],checks:[],depends_on:[],expected_outputs:['Retained content'],
      mode:'synthesis',execution:'parent',instruction:'Read retained content only',source_refs:[],outputs:[{slot:'read',kind:'observation',description:'Actual retained read'}],
      inputs:inputs.manifests.map(item=>({name:'prior',result_ref:item.result_ref}))};
    assert.equal((await controller.execute('plan','plan',{goal:'Inspect granted bytes',output_mode:'text',source_refs:[],nodes:[node]})).details.ok,true);
    assert.equal((await controller.execute('start','start',{step_id:'P',kind:'execute'})).details.ok,true);
    parentActionId=(await controller.readParentInputs()).action.id;
    const resources=join(cwd,'adapter');await cp(resolve(prior,'packages/capstone-agent/src/capstone_agent/resources'),resources,{recursive:true});
    await mkdir(join(resources,'node_modules/@earendil-works'),{recursive:true});
    for(const [name,path] of [['pi-coding-agent','coding-agent'],['pi-ai','ai']])await symlink(join(sdkRoot,path),join(resources,'node_modules/@earendil-works',name),'dir');
    const {configureGeneralResearch}=await import(pathToFileURL(join(resources,'general-research.mjs')).href);
    const channel=join(cwd,'research');await mkdir(channel);for(const name of ['requests','receipts'])await mkdir(join(channel,name));
    const identity={run_id:'run',turn_id:'turn',attempt_id:action.attempt_id,research_id:action.owner.research_id};
    const schema={type:'object',additionalProperties:false,properties:{}};
    await writeFile(join(channel,'binding.json'),JSON.stringify({schema_version:'capability-research-channel/1.0',...identity,
      read_tool_schema:{...schema,properties:{section:{type:'string',enum:['overview','claims','notes','questions','receipt']}}},
      update_tool_schema:{...schema,properties:{changes:{},expected_revision:{}}},progress_tool_schema:schema,depth_tool_schema:schema}));
    await writeFile(join(channel,'view.json'),JSON.stringify({schema_version:'capability-research-view/1.0',...identity,research_revision:0,state:null}));
    config.researchChannelPath=channel;config.applicationPolicy.allowed_tools.push('agent_research_read');
    const settingsManager=sdk.SettingsManager.inMemory(config.settings);
    const loader=new sdk.DefaultResourceLoader({cwd,agentDir:process.env.PI_CODING_AGENT_DIR,settingsManager,noExtensions:true,noSkills:true,
      noPromptTemplates:true,noThemes:true,noContextFiles:true,agentsFilesOverride:()=>({agentsFiles:[]}),
      extensionFactories:[pi=>{configureGeneralResearch(pi,config,{getControllerState:()=>controller.readState(),
        readReference:(...args)=>controller.readReference(...args)});configureGraphParentContext(pi,config,controller);}]});
    await loader.reload();
    const tools=applicationToolOptions(config,createIsolatedNativeTools(sdk,cwd),()=>controller);
    const {session}=await sdk.createAgentSession({cwd,agentDir:process.env.PI_CODING_AGENT_DIR,modelRuntime:runtime,model,
      resourceLoader:loader,settingsManager,...tools,sessionManager:sdk.SessionManager.inMemory()});
    const frames=[],write=process.stdout.write;process.stdout.write=chunk=>{frames.push(JSON.parse(chunk));return true;};
    let summary;
    try{
      const errors=[];await session.bindExtensions({onError:event=>errors.push(event)});session.setActiveToolsByName(['read','agent_research_read']);
      await session.prompt('Inspect the selected retained content.');
      assert.equal(readPath,inputs.handles[0].path,JSON.stringify({errors,last:session.messages.at(-1)}));assert.equal(resolutions,1);
      assert.ok(!JSON.stringify(session.messages).includes('Granted inputs for parent execute action'));
      const current=await controller.readParentInputs(),result=session.messages.filter(item=>item.role==='toolResult').at(-1);
      assert.equal(result.isError,false);const observed=result.details.native_research_source.source_ref;
      const recorded=await controller.execute('record','record',{action_id:current.action.id,outcome:'completed',
        outputs:[{slot:'read',observation_refs:[observed],artifact_refs:[],summary:'Read exact retained bytes',scope:'Selected retained input'}],limitations:[]});
      assert.equal(recorded.details.ok,true,JSON.stringify(recorded));
      const saved=JSON.parse(view.state.notes.at(-1).text),retained=saved.snapshot.results.at(-1);
      assert.deepEqual(retained.consumed_results,inputs.manifests.map(item=>item.result_ref));
      assert.deepEqual(retained.source_versions,inputs.manifests[0].source_versions);
      assert.ok(saved.receipts.some(item=>item.ref===observed&&item.action_id===current.action.id&&item.status==='completed'));
      assert.ok(!JSON.stringify(await controller.readState()).includes(inputs.handles[0].path));
      assert.ok(!JSON.stringify(frames).includes(inputs.handles[0].path));
      assert.equal(saved.receipts.length,1,'Reference inspection must not mint a receipt');
      summary={read:true,kind,receipts:1,parent:true,inspection_only:true,consumed_results:retained.consumed_results};
    }finally{await controller.close();session.dispose();process.stdout.write=write;}
    process.stdout.write(JSON.stringify(summary));
  }else{
  const dispatch=createGraphNodeDispatcher(config,sdk,runtime,{skills:[],emit:()=>{},contextClient:{freeze:()=>assert.fail('No products')}});
  const result=await dispatch({action:{...action,source_refs:[],source_versions:[]},inputs,checkpoint,
    node:{id:action.step_id,instruction:'Read the selected retained input.',questions:['What was saved?'],expected_outputs:['Exact retained content']}});
  assert.equal(result.status,'completed');assert.equal(readPath,inputs.handles[0].path);
  assert.equal(result.receipts.length,1);assert.equal(result.receipts[0].status,'completed');
  process.stdout.write(JSON.stringify({read:true,kind,receipts:result.receipts.length}));
  }
}finally{process.chdir(prior);await rm(cwd,{recursive:true,force:true});}
