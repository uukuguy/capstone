import test from 'node:test';
import assert from 'node:assert/strict';
import {createToolDiscovery} from '../../src/capstone_agent/resources/general-tool-discovery.mjs';
import {mkdtemp,readFile,realpath,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createServer} from 'node:http';
import * as host from '../../src/capstone_agent/resources/general-sdk.mjs';

function fixture(options={}) {
  let calls=0;
  const publications=Object.fromEntries(Array.from({length:20},(_,i)=>['source_'+i,{
    description:'Published source '+i+' '+'x'.repeat(500),
    inputSchema:{type:'object',properties:{query:{type:'string'}},required:['query']},
    outputSchema:{type:'object',properties:{value:{type:'number'}}}}]));
  const tools=Object.entries(publications).map(([name,p])=>({name,label:name,description:p.description,
    parameters:p.inputSchema,execute:async()=>{calls++;return {content:[{type:'text',text:'observed'}]};}}));
  return {controller:createToolDiscovery({tools,publications,admittedNames:Object.keys(publications).slice(0,19),...options}),calls:()=>calls};
}

test('search pages contain only granted bounded published summaries',async()=>{
  const {controller:c}=fixture();
  const search=c.tools.find(t=>t.name==='agent_tool_search');
  const result=JSON.parse((await search.execute('search',{query:'source',offset:0})).content[0].text);
  assert.equal(result.tools.length,8);assert.equal(result.next_offset,8);
  assert.ok(result.tools.every(t=>t.description.length<=240));
  assert.ok(!JSON.stringify(result).includes('inputSchema'));
  const last=JSON.parse((await search.execute('last',{query:'',offset:16})).content[0].text);
  assert.equal(last.tools.length,3);assert.ok(!last.tools.some(t=>t.name==='source_19'));
});

test('arbitrary toolset labels have no client ordering or activation gate',async()=>{
 for(const group of ['readonly_sql','renamed_relation']){
  const publications={alpha:{description:'Data query',inputSchema:{type:'object'},_meta:{'data-gateway/toolset':group}},
   zeta:{description:'Data query',inputSchema:{type:'object'},_meta:{'data-gateway/toolset':'renamed_operation'}}};
  const tools=Object.entries(publications).map(([name,p])=>({name,parameters:p.inputSchema,execute:async()=>({content:[]})}));
  const c=createToolDiscovery({tools,publications,admittedNames:Object.keys(publications)});
  const result=JSON.parse((await c.tools[0].execute('all',{query:'Data'})).content[0].text);
  assert.deepEqual(result.tools.map(t=>t.name),['alpha','zeta']);
  assert.equal(result.tools[0].access,'published_operation');
  const filtered=JSON.parse((await c.tools[0].execute('group',{query:'',toolset:group})).content[0].text);
  assert.deepEqual(filtered.tools.map(t=>t.name),['alpha']);
  const accepted=await c.tools[1].execute('load',{names:['alpha']});
  assert.notEqual(accepted.isError,true);
  assert.equal(JSON.parse(accepted.content[0].text).activation,'next_turn');
  assert.deepEqual(c.admittedTools[0].parameters,publications.alpha.inputSchema);
 }
});

test('selection guidance reaches both discovery and direct activation without banning generic tools',async()=>{
 const publications={renamed_operation:{description:'Compute a business statistic',inputSchema:{type:'object'}},
  renamed_table_reader:{description:'Query a discovered table',inputSchema:{type:'object'}}};
 const tools=Object.entries(publications).map(([name,p])=>({name,parameters:p.inputSchema,execute:async()=>({content:[]})}));
 const c=createToolDiscovery({tools,publications,admittedNames:Object.keys(publications)});
 const search=JSON.parse((await c.tools[0].execute('find',{query:''})).content[0].text);
 const load=JSON.parse((await c.tools[1].execute('load',{names:['renamed_table_reader']})).content[0].text);
 assert.equal(load.selection_guidance,search.selection_guidance);
 assert.match(load.selection_guidance,/current discovery/);
 assert.match(load.selection_guidance,/provider/);
 assert.match(load.selection_guidance,/validate one bounded call/);
 assert.equal(load.activation,'next_turn');
 assert.deepEqual(c.admittedTools.map(tool=>tool.name).sort(),Object.keys(publications).sort());
});

test('activation is atomic and takes effect only at the next loop boundary',async()=>{
  const {controller:c,calls}=fixture();
  const hooks=new Map();let active=c.initialToolNames(['read','source_0','source_19']);
  c.configure({on:(name,fn)=>hooks.set(name,fn),getActiveTools:()=>active,setActiveTools:names=>{active=names;}});
  assert.deepEqual(active,['read','agent_tool_search','agent_tool_load']);
  const load=c.tools.find(t=>t.name==='agent_tool_load');
  const first=c.guardedTools.find(t=>t.name==='source_0');
  await load.execute('load',{names:['source_0']});
  await assert.rejects(first.execute('early',{}),/not active/);
  assert.equal(calls(),0);hooks.get('turn_end')();
  await first.execute('ready',{});assert.equal(calls(),1);
  await assert.rejects(load.execute('forged',{names:['source_1','source_19']}),/not admitted/);
  hooks.get('turn_end')();assert.ok(active.includes('source_0'));assert.ok(!active.includes('source_1'));
  await load.execute('replace',{names:['source_1']});hooks.get('turn_end')();
  await assert.rejects(first.execute('old',{}),/not active/);
  hooks.get('session_shutdown')();
  await assert.rejects(load.execute('stopped',{names:['source_1']}),/closed/);
});

test('inactive tool errors explain replacement menus without changing receipts or grants',async()=>{
  const {controller:c,calls}=fixture();const hooks=new Map();let active=c.initialToolNames(['read']);
  c.configure({on:(name,fn)=>hooks.set(name,fn),getActiveTools:()=>active,setActiveTools:names=>{active=names;}});
  await c.tools[1].execute('first',{names:['source_0']});hooks.get('turn_end')();
  await c.tools[1].execute('replace',{names:['source_1']});hooks.get('turn_end')();
  const message={role:'toolResult',toolName:'source_0',isError:true,content:[{type:'text',text:'Tool source_0 not found'}]};
  const outsider={...message,toolName:'source_19',content:[{type:'text',text:'Tool source_19 not found'}]};
  const before=JSON.stringify(message);
  const result=hooks.get('context')({messages:[message,outsider]});
  assert.equal(JSON.stringify(message),before);assert.equal(result.messages[1],outsider);
  const recovery=JSON.parse(result.messages[0].content[1].text);
  assert.equal(recovery.code,'tool_not_active');assert.deepEqual(recovery.active_tools,['source_1']);
  assert.equal(recovery.recovery.tool,'agent_tool_load');assert.deepEqual(recovery.recovery.arguments,{names:['source_0']});
  assert.equal(recovery.recovery.activation,'next_turn');assert.equal(calls(),0);
  assert.equal(hooks.get('context')({messages:result.messages}),undefined);
});

test('selected complete contracts must fit explicit count and schema budgets',async()=>{
  const {controller:c}=fixture({maxActiveTools:1,maxActiveSchemaChars:100});
  const load=c.tools.find(t=>t.name==='agent_tool_load');
  await assert.rejects(load.execute('many',{names:['source_0','source_1']}),/capacity/);
  await assert.rejects(load.execute('huge',{names:['source_0']}),/capacity/);
});
test('large output contracts remain available by file without expanding the model history',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'output-contract-'));
  try{
    const publication={description:'Source',inputSchema:{type:'object',properties:{}},
      outputSchema:{type:'object',description:'x'.repeat(12000),properties:{value:{type:'number'}}}};
    const tool={name:'source',parameters:publication.inputSchema,execute:async()=>({content:[]})};
    const c=createToolDiscovery({tools:[tool],publications:{source:publication},admittedNames:['source'],cwd:dir});
    const result=await c.tools[1].execute('load-large',{names:['source']});
    assert.ok(JSON.stringify(result.content).length<=6000);
    const projection=JSON.parse(result.content[0].text);
    const full=JSON.parse(await readFile(projection.full_result.path,'utf8'));
    assert.deepEqual(full.tools[0].outputSchema,publication.outputSchema);
    assert.equal(full.activation,'next_turn');
    assert.equal(host.rpcEvent({type:'tool_execution_end',toolName:'agent_tool_load',result}).result.content[0].text,JSON.stringify(full));
  }finally{await rm(dir,{recursive:true,force:true});}
});

test('sessions without any gateway grant do not acquire discovery tools',()=>{
  const config={dataGateway:{onDemandTools:true,catalog:{tools:{ungranted:{description:'No grant',inputSchema:{type:'object'}}}}},
    applicationPolicy:{allowed_tools:['read']}};
  assert.equal(host.createGatewayToolDiscovery(config),undefined);
  config.applicationPolicy.allowed_tools.push('ungranted');
  assert.throws(()=>host.createGatewayToolDiscovery(config),/authorize/);
});

test('accepted research handoff closes pending direct activation before the boundary',async()=>{
  const {controller:c}=fixture();const hooks=new Map();let active=['agent_tool_search','agent_tool_load'];
  const pi={on:(name,fn)=>hooks.set(name,fn),getActiveTools:()=>active,setActiveTools:names=>{active=names;}};
  c.configure(pi);
  host.configureAdaptiveToolHandoff(pi,{researchRuntime:{adaptiveAgentLoop:true,isolatedTaskExecution:true},
    applicationPolicy:{allowed_tools:['agent_tool_search','agent_tool_load','source_0','agent_research_plan']}},c);
  await c.tools.find(t=>t.name==='agent_tool_load').execute('pending',{names:['source_0']});
  hooks.get('tool_result')({toolName:'agent_research_plan',details:{ok:true}});
  hooks.get('turn_end')();assert.deepEqual(active,['agent_research_plan']);
  await assert.rejects(c.tools[0].execute('closed',{query:''}),/closed/);
});

for(const mode of ['parent','managed-child'])test('actual pinned SDK '+mode+' loads an exact granted gateway contract then invokes once on the next turn',async()=>{
  assert.equal(typeof host.createGatewayToolDiscovery,'function');
  const sdk=await import('../../../../.grid-agent/runtime/pi/source/packages/coding-agent/dist/index.js');
  const ai=await import('../../../../.grid-agent/runtime/pi/source/packages/ai/dist/index.js');
  const dir=await mkdtemp(join(mode==='parent'?tmpdir():new URL('../../../../.grid-agent/runtime/',import.meta.url).pathname,'tool-discovery-sdk-'));
  const previousAgentDir=process.env.PI_CODING_AGENT_DIR;
  process.env.PI_CODING_AGENT_DIR=dir;
  const calls=[],menus=[],errors=[],observations=[],recoveries=[];
  const resultBody=JSON.stringify({structuredContent:{status:'partial',data:{unit:'MW',
    points:Array.from({length:5000},(_,i)=>({time:i,value:i+.5}))}}});
  const server=createServer(async(req,res)=>{
    let body='';for await(const chunk of req)body+=chunk;
    const call=JSON.parse(body);calls.push(call);
    res.setHeader('Content-Type','application/json');
    res.end(JSON.stringify({result_json:resultBody,observation:{kind:'external_gateway_observation',
      task_id:'task-sdk',tool_call_id:call.call_id,tool:call.name,catalog_revision:'revision',tool_schema_sha256:'hash-0'}}));
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const publications=Object.fromEntries(Array.from({length:30},(_,i)=>['data_gateway_source_'+i,{
    name:'source_'+i,description:'Published searchable source '+i,
    inputSchema:{type:'object',properties:{query:{type:'string'}},required:['query'],additionalProperties:false},
    outputSchema:{type:'object',properties:{status:{type:'string'}}}}]));
  const config={model:'fixture',toolResultCwd:dir,settings:{compaction:{enabled:false}},extensions:[],allowedSkills:[],contextFiles:[],
    deadlineAt:Date.now()+10000,applicationPolicy:{allowed_tools:[...['agent_tool_search','agent_tool_load'],
    ...Object.keys(publications).slice(0,29)]},dataGateway:{onDemandTools:true,
    url:'http://127.0.0.1:'+server.address().port,grant:'task-only-fixture',taskId:'task-sdk',
    catalog:{revision:'revision',tools:publications,tool_hashes:Object.fromEntries(Object.keys(publications).map((name,i)=>[name,'hash-'+i]))}}};
  const discovery=host.createGatewayToolDiscovery(config);
  const model={id:'fixture',name:'Fixture',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',
    reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
  let index=0;
  const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
    streamSimple(_model,context){
      menus.push(context.tools.map(t=>({name:t.name,parameters:t.parameters})));
      recoveries.push(...context.messages.filter(message=>message.role==='toolResult'&&
        message.content?.some(part=>part.type==='text'&&part.text.includes('"code":"tool_not_active"'))));
      const batches=[
        [{name:'agent_tool_search',arguments:{query:'searchable',offset:0}}],
        [{name:'agent_tool_load',arguments:{names:['data_gateway_source_0']}},
          {name:'data_gateway_source_0',arguments:{query:'too early'}}],
        [{name:'data_gateway_source_0',arguments:{query:'current'}}],
        [{name:'agent_tool_load',arguments:{names:['data_gateway_source_29']}}],
        [{name:'agent_tool_load',arguments:{names:[]}}],
        [{name:'data_gateway_source_0',arguments:{query:'old menu'}}]];
      const batch=batches[index++];
      const message={role:'assistant',content:batch?batch.map((call,i)=>({type:'toolCall',id:'call-'+index+'-'+i,...call})):
        [{type:'text',text:'Observed partial result.'}],api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),
        stopReason:batch?'toolUse':'stop',usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{total:0}}};
      const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
    }};
  let session,owned;
  try{
    if(mode==='managed-child') {
      owned=await host.createManagedChildSession(config,sdk,runtime,{cwd:dir,toolNames:['data_gateway_source_0']});
      session=owned.session;
    }else{
    const settingsManager=sdk.SettingsManager.inMemory({compaction:{enabled:false}});
    const loader=new sdk.DefaultResourceLoader({cwd:dir,agentDir:dir,settingsManager,noExtensions:true,noSkills:true,
      noPromptTemplates:true,noThemes:true,noContextFiles:true,agentsFilesOverride:()=>({agentsFiles:[]}),
      extensionFactories:[pi=>discovery.configure(pi)]});await loader.reload();
    ({session}=await sdk.createAgentSession({cwd:dir,agentDir:dir,modelRuntime:runtime,model,resourceLoader:loader,
      settingsManager,sessionManager:sdk.SessionManager.inMemory(),...host.applicationToolOptions(config,[],undefined,discovery)}));
    await session.bindExtensions({onError:error=>errors.push(error)});
    session.setActiveToolsByName(discovery.initialToolNames(config.applicationPolicy.allowed_tools));
    }
    session.subscribe(event=>{if(event.type==='tool_execution_end'&&event.toolName==='data_gateway_source_0'&&!event.isError)
      observations.push(host.rpcEvent(event));});
    await session.prompt('Read a published source.');
    assert.deepEqual(errors,[]);assert.equal(calls.length,1);assert.equal(calls[0].arguments.query,'current');
    assert.ok(recoveries.length>0,'The real SDK model context must explain an inactive published tool');
    assert.deepEqual(menus[0].map(t=>t.name),['agent_tool_search','agent_tool_load']);
    assert.deepEqual(menus[1],menus[0]);
    assert.deepEqual(menus[2].find(t=>t.name==='data_gateway_source_0').parameters,publications.data_gateway_source_0.inputSchema);
    assert.ok(menus.every(menu=>menu.length<=3));
    assert.ok(menus.every(menu=>!menu.some(t=>t.name==='data_gateway_source_29')));
    const results=session.messages.filter(m=>m.role==='toolResult');
    assert.ok(results.some(m=>m.toolName==='agent_tool_load'&&m.isError));
    assert.ok(results.some(m=>m.toolName==='data_gateway_source_0'&&m.isError));
    assert.equal(results.filter(m=>m.toolName==='data_gateway_source_0'&&!m.isError).length,1);
    const result=results.find(m=>m.toolName==='data_gateway_source_0'&&!m.isError);
    assert.ok(JSON.stringify(result.content).length<=6000,'The actual model history must not contain all data rows');
    const reference=JSON.parse(result.content[0].text).full_result;
    assert.ok(reference.path.startsWith(await realpath(dir)),'Use the selected private child/parent directory');
    assert.equal(await readFile(reference.path,'utf8'),resultBody);
    assert.equal(observations[0].result.content[0].text,resultBody,'The real SDK event restores exact gateway bytes for host verification');
  }finally{if(owned)await owned.close();else session?.dispose();await new Promise(resolve=>server.close(resolve));await rm(dir,{recursive:true,force:true});
    if(previousAgentDir===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=previousAgentDir;}
});

test('repeated searches advise reuse without blocking changed exploration or pagination',async()=>{
 const {controller:c}=fixture();const search=c.tools.find(t=>t.name==='agent_tool_search');
 const run=async(query,offset=0)=>JSON.parse((await search.execute('search',{query,offset})).content[0].text);
 const first=await run('source');assert.equal(first.discovery_feedback,undefined);
 const repeated=await run('source');assert.deepEqual(repeated.tools,first.tools);assert.equal(repeated.discovery_feedback.repeated_query,true);
 assert.equal((await run('source',8)).discovery_feedback,undefined);
 assert.equal((await run('missing')).discovery_feedback,undefined);
 assert.equal((await run('missing')).discovery_feedback.publication_changed,false);
});
