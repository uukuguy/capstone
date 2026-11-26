import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {checkCapacity,runtimeLimits} from '../src/capstone_agent/resources/runtime-limits.mjs';

for(const mode of ['normal','debug'])test(`managed SDK repairs oversized tool input in the same ${mode} task`,async()=>{
  const root=resolve('.grid-agent/runtime/pi/source/packages');
  const sdk=await import(pathToFileURL(resolve(root,'coding-agent/dist/index.js')).href);
  const ai=await import(pathToFileURL(resolve(root,'ai/dist/index.js')).href);
  const adapter=await import('../src/capstone_agent/resources/general-sdk.mjs');
  const cwd=await mkdtemp(resolve(tmpdir(),'capacity-repair-')),previous=process.env.PI_CODING_AGENT_DIR,previousCwd=process.cwd();
  const limits=runtimeLimits({command_bytes:8},{mode}),executed=[];
  const boundedSdk={...sdk,createCodingTools:()=>[{name:'bash',label:'Bounded command',description:'Execute a bounded command',
    parameters:{type:'object',properties:{command:{type:'string'}},required:['command']},
    async execute(_id,args){checkCapacity(limits,'command_bytes',Buffer.byteLength(args.command),'bytes','tool_arguments');
      executed.push(args.command);return {content:[{type:'text',text:'Saved'}],details:{}};}}]};
  const model={id:'capacity-offline',name:'Offline',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
  let turn=0,owned;
  const diagnostics=[],write=process.stderr.write;
  const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
    streamSimple(_model,context){
      const results=context.messages.filter(message=>message.role==='toolResult');
      if(turn===1){assert.equal(results.at(-1).isError,true);assert.match(JSON.stringify(results.at(-1)),/command_bytes/);assert.deepEqual(executed,[]);}
      if(turn===2)assert.equal(results.at(-1).isError,false);
      const content=turn<2?[{type:'toolCall',id:`call-${turn}`,name:'bash',arguments:{command:turn===0?'x'.repeat(9):'valid'}}]:[{type:'text',text:'Completed.'}];
      const message={role:'assistant',content,api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),stopReason:turn++<2?'toolUse':'stop',usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}};
      const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
    }};
  const originalStream=runtime.streamSimple;
  try{
    process.stderr.write=function(chunk,...args){
      if(String(chunk).includes('"type":"capacity_diagnostic"')){diagnostics.push(String(chunk));return true;}
      return write.call(this,chunk,...args);
    };
    process.chdir(cwd);
    process.env.PI_CODING_AGENT_DIR=resolve(cwd,'agent');await mkdir(process.env.PI_CODING_AGENT_DIR);
    const config={model:model.id,runtimeLimitMode:mode,settings:{packages:[],extensions:[],skills:[]},extensions:[],allowedSkills:[],contextFiles:[],systemPrompt:'Use the bounded tool.',applicationPolicy:{allowed_tools:['bash']}};
    owned=await adapter.createManagedChildSession(config,boundedSdk,runtime,{toolNames:['bash'],cwd});
    await owned.session.prompt('Save the result.');
    assert.equal(turn,3);assert.deepEqual(executed,['valid']);assert.equal(runtime.streamSimple,originalStream);
    assert.equal(diagnostics.length,mode==='debug'?1:0);
    if(mode==='debug'){
      assert.ok(Buffer.byteLength(diagnostics[0])<1024);
      assert.deepEqual(JSON.parse(diagnostics[0]),{type:'capacity_diagnostic',code:'capacity_exceeded',mode:'debug',dimension:'command_bytes',actual:9,limit:8,unit:'bytes',phase:'tool_arguments'});
    }
    await owned.close();
    assert.throws(()=>checkCapacity(limits,'command_bytes',9,'bytes','after_close'));
    assert.equal(diagnostics.length,mode==='debug'?1:0);
  }finally{await owned?.close();process.stderr.write=write;process.chdir(previousCwd);if(previous===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=previous;await rm(cwd,{recursive:true,force:true});}
});

test('native prompt frame accepts configured capacity above old fixed frame bound', async () => {
  const {validatePromptFrame} = await import('../src/capstone_agent/resources/general-sdk.mjs');
  const text = '字'.repeat(100000);
  const line = JSON.stringify({type: 'prompt', message: text});
  const frame = validatePromptFrame(line, {input: {kind: 'text', text},
    runtimeLimits: {rpc_frame_bytes: 400000, input_text_chars: 100000}});
  assert.equal(frame.message, text);
});

test('native prompt frame applies exact bytes and Unicode input character overrides', async () => {
  const {validatePromptFrame} = await import('../src/capstone_agent/resources/general-sdk.mjs');
  const text = '🙂'.repeat(11);
  const line = JSON.stringify({type: 'prompt', message: text});
  assert.throws(() => validatePromptFrame(line, {input: {kind: 'text', text},
    runtimeLimits: {rpc_frame_bytes: Buffer.byteLength(line) - 1, input_text_chars: 20}}),
  error => error.capacity.dimension === 'rpc_frame_bytes' && error.capacity.actual === Buffer.byteLength(line));
  assert.throws(() => validatePromptFrame(line, {input: {kind: 'text', text},
    runtimeLimits: {rpc_frame_bytes: 1000, input_text_chars: 10}}),
  error => error.capacity.dimension === 'input_text_chars' && error.capacity.actual === 11 && error.capacity.limit === 10);
  assert.equal(validatePromptFrame(line, {input: {kind: 'text', text},
    runtimeLimits: {rpc_frame_bytes: Buffer.byteLength(line), input_text_chars: 11}}).message, text);
});

test('admitted guides preserve first-load order before interaction',async()=>{
  const {createGuideProjection}=await import('../src/capstone_agent/resources/model-context-input.mjs');
  const projection=createGuideProjection({presentation:'PPT guide.',capacity:'Capacity guide.'});
  const original={systemPrompt:'Stable rules.',messages:[{role:'user',content:'Question'}]};
  assert.equal(projection.project(original),original);
  assert.equal(projection.load('unknown'),false);
  assert.equal(projection.load('capacity'),true);
  const first=projection.project(original);
  assert.equal(first.systemPrompt,'Stable rules.\n\nCapacity guide.');
  projection.load('presentation');
  projection.load('capacity');
  const second=projection.project(original);
  assert.equal(second.systemPrompt,first.systemPrompt+'\n\nPPT guide.');
  assert.equal(second.messages,original.messages);
});

test('gateway guide is a zero-argument reader limited to the granted tool',async()=>{
  const {applicationToolOptions}=await import('../src/capstone_agent/resources/general-sdk.mjs');
  const name='agent_gateway_guide';
  let loaded=0;
  const cfg={loadGatewayGuide:()=>{loaded++;},applicationPolicy:{allowed_tools:[]}};
  assert.ok(!applicationToolOptions(cfg,[]).customTools.some(tool=>tool.name===name));
  cfg.applicationPolicy.allowed_tools.push(name);
  const tool=applicationToolOptions(cfg,[]).customTools.find(tool=>tool.name===name);
  assert.deepEqual(tool.parameters,{type:'object',properties:{},additionalProperties:false});
  await tool.execute('read',{},new AbortController().signal);
  assert.equal(loaded,1);
});

test('thin runtime exposes only resident and explicitly loaded admitted contracts',async()=>{
  const {createThinToolView}=await import('../src/capstone_agent/resources/general-sdk.mjs');
  const a={name:'write',label:'Write a task file',description:'Save a relative path.',parameters:{type:'object'}};
  const b={name:'run',label:'Run a task command',description:'Execute a fixed operation.',parameters:{type:'object'}};
  const search={name:'agent_tool_search',parameters:{type:'object'}};
  const runtimeTools={name:'agent_runtime_tools',parameters:{type:'object'}};
  const view=createThinToolView(['agent_runtime_tools','agent_tool_search','write'],['agent_tool_search']);
  assert.deepEqual(view.project({tools:[search,a,b]}).tools,[search]);
  const catalogue=await view.tool.execute('catalog',{});
  assert.match(catalogue.content[0].text,/Write a task file/);
  assert.doesNotMatch(catalogue.content[0].text,/Run a task command/);
  const seen=[];
  const loader=view.loader({
    name:'agent_tool_load',label:'Loader',parameters:{},
    async execute(_id,args){
      seen.push(args.names);
      if(args.names.includes('run'))return {isError:true};
      return {content:[{type:'text',text:'Remote contract ready.'}]};
    },
  });
  assert.ok(!Object.hasOwn(view.tool.parameters.properties,'names'));
  const denied=await loader.execute('denied',{names:['write','run']});
  assert.equal(denied.isError,true);
  assert.deepEqual(view.project({tools:[search,a,b]}).tools,[search]);
  await loader.execute('load',{names:['write','data_gateway_existing']});
  assert.deepEqual(seen,[['run'],['data_gateway_existing']]);
  const repeated=await loader.execute('local',{names:['write']});
  assert.deepEqual(JSON.parse(repeated.content[0].text),{
    loaded:['write'],newly_loaded:[],already_active:['write'],
  });
  assert.deepEqual(view.project({tools:[search,a,b]}).tools,[search,a]);
  assert.deepEqual(view.project({tools:[a,search,runtimeTools]}).tools,[runtimeTools,search,a]);
  assert.deepEqual(view.project({tools:[search,runtimeTools,a]}).tools,[runtimeTools,search,a]);
  const revised={...a,parameters:{type:'object',required:['path']}};
  assert.deepEqual(view.project({tools:[search,revised,b]}).tools,[search]);
  await loader.execute('reload',{names:['write']});
  assert.deepEqual(view.project({tools:[search,revised,b]}).tools,[search,revised]);
  assert.deepEqual(view.project({tools:[search]}).tools,[search]);
  assert.deepEqual(view.project({tools:[search,revised]}).tools,[search]);
});

test('thin tool replacement frees native slots and rejects unadmitted residents',async()=>{
  const {createThinToolView}=await import('../src/capstone_agent/resources/general-sdk.mjs');
  const tools=['write','read','denied'].map(name=>({name}));
  const view=createThinToolView(['write','read'],['denied'],undefined,1);
  assert.deepEqual(view.project({tools}).tools,[]);
  const loader=view.loader();
  await loader.execute('first',{names:['write']});
  assert.equal((await loader.execute('oversize',{names:['read']})).isError,true);
  assert.equal((await loader.execute('unknown',{names:['denied'],replace:true})).isError,true);
  assert.deepEqual(view.project({tools}).tools,[tools[0]]);
  const replaced=await loader.execute('replace',{names:['read'],replace:true});
  assert.equal(replaced.isError,undefined);
  assert.deepEqual(view.project({tools}).tools,[tools[1]]);
});

test('append-only guides deduplicate only while their exact observation remains in active history',async()=>{
  const {createGuideReader}=await import('../src/capstone_agent/resources/model-context-input.mjs');
  const {createThinToolView}=await import('../src/capstone_agent/resources/general-sdk.mjs');
  let messages=[];
  const read=createGuideReader({'runtime-guide':'Use the actual task paths.'},()=>messages);
  const history=Array.from({length:6},(_,index)=>({role:'user',content:'record '+index,internal:'hidden'}));
  const view=createThinToolView([],[],()=>read('runtime-guide'),16,history);
  const earlier=await view.tool.execute('history',{history_index:1});
  assert.deepEqual(JSON.parse(earlier.content[0].text),{history_index:1,record:{role:'user',content:'record 1'}});
  assert.equal((await view.tool.execute('outside',{history_index:2})).isError,true);
  const request={systemPrompt:'Stable',messages,tools:[]};
  const first=await view.tool.execute('first',{guide:true});
  assert.match(first.content[0].text,/Use the actual task paths\./);
  assert.match(first.content[0].text,/runtime-guide@sha256:[a-f0-9]{64}/);
  assert.deepEqual(view.project(request),request);
  messages=[{role:'toolResult',content:first.content}];
  const repeated=await view.tool.execute('repeat',{guide:true});
  assert.match(repeated.content[0].text,/already in active history/);
  assert.doesNotMatch(repeated.content[0].text,/actual task paths/);
  messages=[];
  assert.deepEqual(await view.tool.execute('after-compaction',{guide:true}),first);
  const both=await view.tool.execute('both',{guide:true,include_tools:true});
  assert.deepEqual(both.content,[...first.content,...(await view.tool.execute('catalog',{})).content]);
});

test('managed thin parent activates tools and automatically compacts at the threshold',async()=>{
  const {Readable}=await import('node:stream');
  const root=resolve('.grid-agent/runtime/pi/source/packages');
  const sdk=await import(pathToFileURL(resolve(root,'coding-agent/dist/index.js')).href);
  const ai=await import(pathToFileURL(resolve(root,'ai/dist/index.js')).href);
  const {runManagedSession}=await import('../src/capstone_agent/resources/general-sdk.mjs');
  const cwd=await mkdtemp(resolve(tmpdir(),'thin-parent-'));
  const previousCwd=process.cwd(), previousAgent=process.env.PI_CODING_AGENT_DIR;
  const stdin=Object.getOwnPropertyDescriptor(process,'stdin');
  const model={id:'thin-fixture',name:'Offline',provider:'capstone-general',api:'openai-completions',
    baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024};
  const requests=[], events=[];
  const stdoutWrite=process.stdout.write;
  let writes=0;
  const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,
    getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
    streamSimple(_model,context){
      requests.push(context);
      const contents=[
        {type:'toolCall',id:'load',name:'agent_tool_load',arguments:{names:['write']}},
        {type:'toolCall',id:'save',name:'write',arguments:{}},
        {type:'text',text:'Summary: the product was saved.'},
        {type:'text',text:'Saved the product.'},
      ];
      const stopReason=requests.length<3?'toolUse':'stop';
      const message={role:'assistant',content:[contents[requests.length-1]],api:model.api,
        provider:model.provider,model:model.id,timestamp:Date.now(),stopReason,
        usage:{input:requests.length===2?31500:0,output:0,cacheRead:0,cacheWrite:0,
          totalTokens:requests.length===2?31500:0,cost:{total:0}}};
      const stream=ai.createAssistantMessageEventStream();
      stream.push({type:'done',reason:stopReason,message});
      stream.end();
      return stream;
    }};
  const write={name:'write',label:'Write',description:'Save the product.',parameters:{type:'object'},
    async execute(){writes++;return {content:[{type:'text',text:'Product saved.'}]};}};
  try{
    process.stdout.write=function(chunk,...args){
      const line=String(chunk);
      if(!line.startsWith('{"type":'))return stdoutWrite.call(this,chunk,...args);
      events.push(JSON.parse(line));
      return true;
    };
    process.chdir(cwd);
    process.env.PI_CODING_AGENT_DIR=resolve(cwd,'agent');
    await mkdir(process.env.PI_CODING_AGENT_DIR);
    Object.defineProperty(process,'stdin',{value:Readable.from(['{"type":"prompt","message":"trigger"}\n']),configurable:true});
    await runManagedSession({model:model.id,thinInitialContext:true,settings:{compaction:{enabled:true,reserveTokens:1024,keepRecentTokens:16}},
      extensions:[],allowedSkills:[],contextFiles:[
        {path:'admitted-gateway-operations',content:'Host-admitted operation fixture-ref'},
        {path:'gateway-contract-context',content:'Host-admitted contract index'},
        {path:'registered-gateway-progressive-discovery',content:'Use the existing negotiated gateway index'},
      ],systemPrompt:'Save the requested product.',
      applicationPolicy:{allowed_tools:['agent_runtime_tools','agent_tool_load','bash','write']},
      input:{kind:'text',text:'Save the product.'}}, {...sdk,createCodingTools:()=>[write,{...write,name:'bash'}]},runtime);
    assert.deepEqual(requests.map(request=>request.tools?.some(tool=>tool.name==='write')??false),[false,true,false,true]);
    assert.equal(writes,1);
    assert.ok(requests[0].tools.some(tool=>tool.name==='bash'));
    assert.match(requests[0].systemPrompt,/capstone-workspace-products\/1/);
    assert.match(requests[0].systemPrompt,/Host-admitted operation fixture-ref/);
    assert.match(requests[0].systemPrompt,/Host-admitted contract index/);
    assert.match(requests[0].systemPrompt,/Use the existing negotiated gateway index/);
    assert.ok(events.some(event=>event.type==='compaction_end'&&event.reason==='threshold'&&event.status==='completed'));
    assert.ok(events.some(event=>event.type==='model_context_usage'&&event.kind==='summary'&&event.state==='completed'));
    assert.match(JSON.stringify(requests[3].messages),/Summary: the product was saved/);
    assert.match(JSON.stringify(requests[2].messages),/Save the product/);
  }finally{
    process.stdout.write=stdoutWrite;
    Object.defineProperty(process,'stdin',stdin);
    process.chdir(previousCwd);
    if(previousAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;
    else process.env.PI_CODING_AGENT_DIR=previousAgent;
    await rm(cwd,{recursive:true,force:true});
  }
});
