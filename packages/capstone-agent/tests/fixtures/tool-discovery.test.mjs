import test from 'node:test';
import assert from 'node:assert/strict';
import {createToolDiscovery} from '../../src/capstone_agent/resources/general-tool-discovery.mjs';
import {mkdtemp,readFile,realpath,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createServer} from 'node:http';
import * as host from '../../src/capstone_agent/resources/general-sdk.mjs';
import {compositionPolicy} from '../../src/capstone_agent/resources/tool-composition.mjs';

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

test('domain publications use bounded discovery without gateway grants or eager schemas',async()=>{
 const schema={type:'object',properties:{model:{type:'string'}},required:['model'],additionalProperties:false};
 const config={applicationPolicy:{allowed_tools:['bash','agent_tool_search','agent_tool_load','pack_inspect']},
  domainTools:{onDemandTools:true,catalog:{tools:{pack_inspect:{description:'Inspect the registered model',inputSchema:schema},
    pack_private:{description:'Unadmitted action',inputSchema:schema}},tool_hashes:{pack_inspect:'exact-revision'}}}};
 const discovery=host.createApplicationToolDiscovery(config);
 assert.ok(discovery);
 assert.deepEqual(discovery.initialToolNames(config.applicationPolicy.allowed_tools),['bash','agent_tool_search','agent_tool_load']);
 const search=JSON.parse((await discovery.tools[0].execute('search',{query:'registered model'})).content[0].text);
 assert.deepEqual(search.tools.map(t=>t.name),['pack_inspect']);
 const options=host.applicationToolOptions(config,[],undefined,discovery);
 assert.equal(options.customTools.filter(t=>t.name==='pack_inspect').length,1);
 assert.equal(options.customTools.some(t=>t.name==='pack_private'),false);
 await assert.rejects(options.customTools.find(t=>t.name==='pack_inspect').execute('early',{model:'m'}),/tool_not_active/);
 const loaded=await discovery.tools[1].execute('load',{names:['pack_inspect']});
 assert.ok(JSON.stringify(loaded).includes('exact-revision'));
 assert.deepEqual(options.customTools.find(t=>t.name==='pack_inspect').parameters,schema);
 assert.deepEqual(discovery.admittedTools.map(t=>t.name),['pack_inspect']);
 discovery.close();
});

test('mixed discovery preserves gateway composition scope and rejects identity collisions',async t=>{
 const cwd=await mkdtemp(join(tmpdir(),'mixed-discovery-'));t.after(()=>rm(cwd,{recursive:true,force:true}));
 const publication={description:'Read admitted data',inputSchema:{type:'object'}};
 const config={toolResultCwd:cwd,deadlineAt:Date.now()+10000,toolComposition:compositionPolicy,
  applicationPolicy:{allowed_tools:['bash','write','agent_tool_search','agent_tool_load','agent_tools_execute','source_read','pack_inspect']},
  dataGateway:{onDemandTools:true,catalog:{revision:'fixture',tools:{source_read:publication},entry_tools:['source_read']}},
  domainTools:{onDemandTools:true,catalog:{tools:{pack_inspect:publication}}}};
 const discovery=host.createApplicationToolDiscovery(config);
 assert.deepEqual(discovery.initialToolNames(['source_read','pack_inspect']),['agent_tool_search','agent_tool_load','source_read']);
 const options=host.applicationToolOptions(config,[],undefined,discovery);
 const tool=options.customTools.find(t=>t.name==='agent_tools_execute');assert.ok(tool);
 const result=await tool.execute('blocked',{calls:[{id:'domain',tool:'pack_inspect',arguments:{}}]});
 assert.equal(result.isError,true);assert.match(JSON.stringify(result),/not admitted|not published|not granted/i);
 discovery.close();
 config.domainTools.catalog.tools.source_read=publication;
 assert.throws(()=>host.createApplicationToolDiscovery(config),/conflicting registered identities/);
});

test('an explicit identity inside a search is not replaced by description references',async()=>{
 const publications={a_related:{name:'related',description:'Use requested_action contract fields'},
  z_requested:{name:'requested_action',description:'Read an exact snapshot'},
  hidden:{name:'private_action',description:'requested_action contract fields'}};
 const c=createToolDiscovery({publications,tools:Object.keys(publications).map(name=>({name})),
  admittedNames:['a_related','z_requested'],pageSize:1});
 const result=JSON.parse((await c.tools[0].execute('find',{query:'requested_action contract fields'})).content[0].text);
 assert.deepEqual(result.tools.map(t=>t.name),['z_requested']);
 assert.equal(result.match_mode,'identity_terms');assert.equal(result.total,1);
 const hidden=JSON.parse((await c.tools[0].execute('find',{query:'private_action'})).content[0].text);
 assert.equal(hidden.total,0);
});

test('unresolved publications load exact contracts before registration without placeholder schemas',async t=>{
 const cwd=await mkdtemp(join(tmpdir(),'progressive-discovery-'));t.after(()=>rm(cwd,{recursive:true,force:true}));
 const publications={selected:{name:'source',description:'Read selected',progressive:{tool_key:'key'}}};
 const registrations=[],hooks=new Map();let reads=0;
 const c=createToolDiscovery({cwd,publications,tools:[{name:'selected',execute:async()=>({content:[]})}],admittedNames:['selected'],
  resolveContracts:async names=>{reads++;assert.deepEqual(names,['selected']);return {selected:{...publications.selected,inputSchema:{type:'object',required:['value']}}};}});
 c.configure({on:(name,fn)=>hooks.set(name,fn),registerTool:t=>registrations.push(t),getActiveTools:()=>[],setActiveTools:()=>{}});
 assert.equal(c.guardedTools.length,0);
 await c.tools[1].execute('load',{names:['selected']});
 assert.equal(reads,1);assert.equal(registrations.length,1);
 assert.deepEqual(registrations[0].parameters,{type:'object',required:['value']});
 await c.tools[1].execute('load-again',{names:['selected']});assert.equal(reads,1);
});

for(const source of ['gateway','domain'])test('actual pinned SDK loads exact contracts before calling '+source+' tools',async()=>{
 const sdk=await import('../../../../.grid-agent/runtime/pi/source/packages/coding-agent/dist/index.js');
 const ai=await import('../../../../.grid-agent/runtime/pi/source/packages/ai/dist/index.js');
 const dir=await mkdtemp(join(tmpdir(),'progressive-sdk-'));
 const menus=[],requests=[],errors=[];let session;
 const toolName=source==='gateway'?'data_gateway_selected':'pack_selected';
 const metadata={name:'selected',description:'Selected action',
  _meta:{'data-gateway/capability':{summary_version:'capability-summary/1',declaration_basis:'provider_declared',
   semantics:{prerequisites:['Use a current issued reference.'],execution_choice:'Use only for the selected scope.'}}},
  progressive:{tool_key:'key',tool_contract_revision:'rev'}};
 const inputSchema={type:'object',properties:{value:{type:'integer'}},required:['value'],additionalProperties:false};
 const server=createServer(async(req,res)=>{
  let raw='';for await(const chunk of req)raw+=chunk;
  const body=JSON.parse(raw);requests.push(body);res.setHeader('Content-Type','application/json');
  res.end(JSON.stringify(body.operation==='resolve_contracts'?{catalog_revision:'pub',executed:false,
   tools:{data_gateway_selected:{...metadata,inputSchema,usage:{rules:'EXACT_USAGE_SENTINEL'}}},tool_hashes:{data_gateway_selected:'rev'}}:
   {tool:body.name,call_id:body.call_id,result_json:JSON.stringify({structuredContent:{status:'ok',data:{value:4}}}),observation:{kind:'external_gateway_observation',
    task_id:'task',tool_call_id:body.call_id,tool:body.name,catalog_revision:'pub',tool_schema_sha256:'rev'}}));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const publication=source==='gateway'?metadata:{name:'selected',description:'Selected domain action',inputSchema};
 const config={toolResultCwd:dir,deadlineAt:Date.now()+10000,applicationPolicy:{allowed_tools:['agent_tool_search','agent_tool_load',toolName]},
  [source==='gateway'?'dataGateway':'domainTools']:{onDemandTools:true,url:'http://127.0.0.1:'+server.address().port,grant:'fixture',taskId:'task',
   catalog:{revision:'pub',tools:{[toolName]:publication},entry_tools:[],tool_hashes:{[toolName]:'rev'}}}};
 const discovery=host.createApplicationToolDiscovery(config);
 const model={id:'fixture',name:'Fixture',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',
  reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
 let turn=0;
 const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline'}}),isUsingOAuth:()=>false,
  streamSimple(_model,context){
   menus.push(context.tools.map(t=>({name:t.name,parameters:t.parameters,description:t.description})));
   if(turn===1&&source==='gateway')assert.ok(JSON.stringify(context.messages).includes('EXACT_USAGE_SENTINEL'));
   const call=[{name:'agent_tool_load',arguments:{names:['selected']}},{name:toolName,arguments:{value:4}}][turn++];
   const message={role:'assistant',content:call?[{type:'toolCall',id:'call-'+turn,...call}]:[{type:'text',text:'Done'}],
    api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),stopReason:call?'toolUse':'stop',
    usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{total:0}}};
   const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
  }};
 try{
  const settingsManager=sdk.SettingsManager.inMemory({compaction:{enabled:false}});
  const loader=new sdk.DefaultResourceLoader({cwd:dir,agentDir:dir,settingsManager,noExtensions:true,noSkills:true,
   noPromptTemplates:true,noThemes:true,noContextFiles:true,agentsFilesOverride:()=>({agentsFiles:[]}),extensionFactories:[pi=>discovery.configure(pi)]});
  await loader.reload();
  ({session}=await sdk.createAgentSession({cwd:dir,agentDir:dir,modelRuntime:runtime,model,resourceLoader:loader,
   settingsManager,sessionManager:sdk.SessionManager.inMemory(),...host.applicationToolOptions(config,[],undefined,discovery)}));
  await session.bindExtensions({onError:error=>errors.push(error)});
  session.setActiveToolsByName(discovery.initialToolNames(config.applicationPolicy.allowed_tools));discovery.installSession(session);
  await session.prompt('Use selected action');
  assert.deepEqual(errors,[]);assert.deepEqual(menus[0].map(t=>t.name),['agent_tool_search','agent_tool_load']);
  assert.deepEqual(menus[1].find(t=>t.name===toolName)?.parameters,inputSchema);
  if(source==='gateway'){
   assert.ok(menus[1].find(t=>t.name===toolName)?.description.includes('Use a current issued reference.'));
   assert.equal(requests.length,2);assert.equal(requests[0].operation,'resolve_contracts');
  }else assert.equal(requests.length,1);
  assert.equal(requests.at(-1).name,toolName);assert.deepEqual(requests.at(-1).arguments,{value:4});
 }finally{session?.dispose();await new Promise(resolve=>server.close(resolve));await rm(dir,{recursive:true,force:true});}
});

test('capability search uses bounded published metadata and isolates grants and snapshots',async()=>{
  const publications={alpha:{name:'opaque_alpha',description:'Operation',
    _meta:{usage:{purpose:'period comparison',constraints:'x'.repeat(300)}}},
    private:{name:'opaque_private',description:'Operation',_meta:{usage:'period comparison'}}};
  const build=(source,admittedNames)=>createToolDiscovery({publications:source,
    tools:Object.keys(source).map(name=>({name})),admittedNames,maxSummaryChars:80});
  const c=build(publications,['alpha']);
  const search=async controller=>JSON.parse((await controller.tools[0].execute('capabilities',{query:'period comparison'})).content[0].text);
  publications.alpha._meta.usage.purpose='changed after snapshot';
  const result=await search(c);
  assert.deepEqual(result.tools.map(t=>t.name),['alpha']);
  assert.ok(result.tools[0].published_metadata_preview.includes('period comparison'));
  assert.ok(result.tools[0].published_metadata_preview.length<=80);
  assert.equal(result.tools[0].published_metadata_truncated,true);
  assert.equal((await search(build({beta:{name:'opaque_beta',description:'unrelated'}},['beta']))).total,0);
});

test('search returns bounded best partial matches and current activation without changing grants',async()=>{
  const publications={entry:{name:'published_entry',description:'Discover service catalog',inputSchema:{type:'object'}},
    check:{name:'published_check',description:'Check service contract time',inputSchema:{type:'object'}},
    hidden:{name:'private_check',description:'Discover service contract check',inputSchema:{type:'object'}}};
  let calls=0;
  const c=createToolDiscovery({publications,tools:Object.keys(publications).map(name=>({name,execute:async()=>{calls++;}})),
    admittedNames:['entry','check'],initialNames:['entry'],pageSize:1});
  const hooks=new Map();c.configure({on:(name,fn)=>hooks.set(name,fn),getActiveTools:()=>[],setActiveTools:()=>{}});
  const search=async query=>JSON.parse((await c.tools[0].execute('find',{query})).content[0].text);
  const partial=await search('service discover contract check');
  assert.equal(partial.match_mode,'identity_terms');
  assert.deepEqual(partial.tools.map(t=>t.name),['check']);
  assert.deepEqual(partial.tools[0].matched_terms,['service','contract','check']);
  assert.equal(partial.tools[0].active,false);
  assert.deepEqual(partial.active_entry_tools,['entry']);
  assert.equal((await search('published_entry')).tools[0].active,true);
  assert.equal((await search('published_entry')).match_mode,'exact_name');
  assert.equal((await search('unrelated')).total,0);
  await c.tools[1].execute('load',{names:['check']});
  assert.equal((await search('published_check')).tools[0].active,false);
  hooks.get('turn_end')();
  assert.equal((await search('published_check')).tools[0].active,true);
  assert.equal(calls,0);
});

test('partial matching preserves toolset filters and bounded pagination',async()=>{
  const publications=Object.fromEntries(['a','b','c'].map((name,i)=>[name,{name:'published_'+name,
    description:'check contract',_meta:{'data-gateway/toolset':i<2?'one':'two'},inputSchema:{type:'object'}}]));
  const c=createToolDiscovery({publications,tools:Object.keys(publications).map(name=>({name})),
    admittedNames:Object.keys(publications),pageSize:1});
  const search=async offset=>JSON.parse((await c.tools[0].execute('find',{query:'check contract missing',toolset:'one',offset})).content[0].text);
  const first=await search(0),second=await search(1);
  assert.equal(first.match_mode,'partial_terms');assert.equal(first.total,2);
  assert.deepEqual(first.tools.map(t=>t.name),['a']);assert.equal(first.next_offset,1);
  assert.deepEqual(second.tools.map(t=>t.name),['b']);assert.equal(second.next_offset,null);
});

test('large granted catalogs support default256 and configured1024 without a hidden24k limit',async()=>{
  for(const count of [256,1024]){
    const publications=Object.fromEntries(Array.from({length:count},(_,i)=>[`registered_${i}`,{
      name:`original_${i}`,description:'x'.repeat(100),inputSchema:{type:'object'},
      outputSchema:{type:'object',description:'y'.repeat(300)}}]));
    const tools=Object.keys(publications).map(name=>({name,execute:async()=>({content:[]})}));
    const cwd=await mkdtemp(join(tmpdir(),'large-discovery-'));
    try{
      const c=createToolDiscovery({tools,publications,admittedNames:Object.keys(publications),cwd,
        ...(count===1024?{maxActiveTools:1024}:{}),initialNames:['registered_0','registered_1']});
      const result=await c.tools[1].execute('large',{names:Object.keys(publications)});
      assert.notEqual(result.isError,true);
      assert.equal(c.tools[1].parameters.properties.names.maxItems,count);
    }finally{await rm(cwd,{recursive:true,force:true});}
  }
});

test('load count errors and discovery explain actual count, retained entries and remaining capacity',async()=>{
  const {controller:c}=fixture({initialNames:['source_0','source_1'],maxActiveTools:3});
  const search=JSON.parse((await c.tools[0].execute('capacity',{query:''})).content[0].text);
  assert.deepEqual(search.capacity,{max_tools:3,entry_tools:2,selectable_tools:1});
  await assert.rejects(c.tools[1].execute('overflow',{names:['source_2','source_3']}),/actual=4.*limit=3.*entry_tools=2.*selectable_tools=1/);
});

test('SDK discovery uses the application capacity snapshot instead of module defaults',()=>{
  const tools=Object.fromEntries(Array.from({length:4},(_,i)=>[`registered_${i}`,{
    name:`source_${i}`,description:'A source',inputSchema:{type:'object'}}]));
  const config={dataGateway:{onDemandTools:true,catalog:{tools,entry_tools:['registered_0']}},
    applicationPolicy:{allowed_tools:['agent_tool_search','agent_tool_load',...Object.keys(tools)]},
    runtimeLimits:{tool_active_count:1024,tool_schema_chars:1000000,tool_search_page_items:10,tool_summary_chars:500}};
  assert.equal(host.createApplicationToolDiscovery(config).tools[1].parameters.properties.names.maxItems,1024);
});

test('rejected selection names are explicit and do not activate any tool',async()=>{
  const {controller:c,calls}=fixture();
  await assert.rejects(c.tools[1].execute('bad',{names:['source_0','missing','source_19']}),
    /not admitted.*missing.*source_19/);
  await assert.rejects(c.guardedTools.find(t=>t.name==='source_0').execute('still-inactive',{}),/not active/);
  assert.equal(calls(),0);
});

test('load resolves published names to admitted registration names without a prefix convention',async()=>{
  const publications={'transport_random':{name:'source_random',inputSchema:{type:'object'}},
    'other_transport':{name:'other_source',inputSchema:{type:'object'}}};
  const tools=Object.keys(publications).map(name=>({name,execute:async()=>({content:[]})}));
  const c=createToolDiscovery({tools,publications,admittedNames:['transport_random']});
  const hooks=new Map();let active=[];
  c.configure({on:(n,f)=>hooks.set(n,f),getActiveTools:()=>active,setActiveTools:n=>active=n});
  const args={names:['source_random','transport_random']};
  const result=JSON.parse((await c.tools[1].execute('load',args)).content[0].text);
  assert.deepEqual(result.tools.map(t=>t.name),['transport_random']);
  assert.deepEqual(args.names,['source_random','transport_random']);
  hooks.get('turn_end')();
  assert.ok(active.includes('transport_random'));
  await c.guardedTools[0].execute('run',{});
  await assert.rejects(c.tools[1].execute('denied',{names:['other_source']}),/not admitted/);
});

test('ambiguous published names reject the complete activation atomically',async()=>{
  for(const collision of [false,true]){
    const publications={one:{name:collision?'two':'shared',inputSchema:{type:'object'}},
      two:{name:collision?'original_two':'shared',inputSchema:{type:'object'}}};
    const tools=Object.keys(publications).map(name=>({name,execute:async()=>({content:[]})}));
    const c=createToolDiscovery({tools,publications,admittedNames:['one','two']});
    await assert.rejects(c.tools[1].execute('load',{names:['one',collision?'two':'shared']}),/ambiguous/i);
    await assert.rejects(c.guardedTools[0].execute('run',{}),/not active/);
  }
});

test('admitted initial tools are callable immediately and survive replacement',async()=>{
  const {controller:c,calls}=fixture({initialNames:['source_0','source_19','missing']});
  const hooks=new Map();let active=c.initialToolNames(['read']);
  c.configure({on:(name,fn)=>hooks.set(name,fn),getActiveTools:()=>active,setActiveTools:names=>{active=names;}});
  assert.deepEqual(active,['read','agent_tool_search','agent_tool_load','source_0']);
  await c.guardedTools.find(t=>t.name==='source_0').execute('startup',{});
  assert.equal(calls(),1);
  await c.tools[1].execute('replace',{names:['source_1']});hooks.get('turn_end')();
  assert.ok(active.includes('source_0'));assert.ok(active.includes('source_1'));
  await c.tools[1].execute('clear',{names:[]});hooks.get('turn_end')();
  assert.ok(active.includes('source_0'));assert.ok(!active.includes('source_1'));
  assert.match(hooks.get('before_agent_start')({}).systemPrompt,/already active/);
});

test('available entries do not impose a service-first workflow on the current instruction',()=>{
  const {controller:c}=fixture({initialNames:['source_0']});const hooks=new Map();
  c.configure({on:(name,fn)=>hooks.set(name,fn)});
  const prompt=hooks.get('before_agent_start')({systemPrompt:'CURRENT_INSTRUCTION_CONTEXT'}).systemPrompt;
  assert.ok(prompt.startsWith('CURRENT_INSTRUCTION_CONTEXT'));
  assert.match(prompt,/Choose tools and skills for the current instruction/);
  assert.match(prompt,/Availability does not require a call/);
  assert.match(prompt,/Only after selecting this service as relevant/);
  assert.doesNotMatch(prompt,/Follow their registered initialization first/);
});

test('initial tool contracts share activation capacity with dynamic selections',async()=>{
  assert.throws(()=>fixture({initialNames:['source_0','source_1'],maxActiveTools:1}),/capacity/);
  assert.throws(()=>fixture({initialNames:['source_0'],maxActiveSchemaChars:100}),/capacity/);
  assert.throws(()=>fixture({initialNames:'source_0'}),/initial/i);
  const {controller:c}=fixture({initialNames:['source_0'],maxActiveTools:1});
  await assert.rejects(c.tools[1].execute('overflow',{names:['source_1']}),/capacity/);
  await c.tools[1].execute('same',{names:['source_0']});
  const {controller:bounded}=fixture({initialNames:['source_0'],maxActiveSchemaChars:1200});
  await assert.rejects(bounded.tools[1].execute('schema-overflow',{names:['source_1']}),/schema capacity/);
});

test('search pages contain only granted bounded published summaries',async()=>{
  const {controller:c}=fixture({pageSize:8,maxSummaryChars:240});
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

test('full guidance stays in task context while search and activation return compact receipts',async()=>{
 const publications={renamed_operation:{description:'Compute a business statistic',inputSchema:{type:'object'}},
  renamed_table_reader:{description:'Query a discovered table',inputSchema:{type:'object'}}};
 const tools=Object.entries(publications).map(([name,p])=>({name,parameters:p.inputSchema,execute:async()=>({content:[]})}));
 const c=createToolDiscovery({tools,publications,admittedNames:Object.keys(publications)});
 const hooks=new Map();c.configure({on:(name,fn)=>hooks.set(name,fn),getActiveTools:()=>[],setActiveTools:()=>{}});
 const search=JSON.parse((await c.tools[0].execute('find',{query:''})).content[0].text);
 const load=JSON.parse((await c.tools[1].execute('load',{names:['renamed_table_reader']})).content[0].text);
 assert.equal(load.selection_guidance,search.selection_guidance);
 assert.ok(load.selection_guidance.length<400);
 const prompt=hooks.get('before_agent_start')({systemPrompt:'Current instruction'}).systemPrompt;
 assert.match(prompt,/current admitted capability index/);
 assert.match(prompt,/discovery response only for information missing/);
 assert.match(prompt,/provider/);
 assert.match(prompt,/validate one bounded call/);
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
  await first.execute('old',{});
  assert.equal(calls(),2);assert.ok(active.includes('source_0'));assert.ok(active.includes('source_1'));
  hooks.get('session_shutdown')();
  await assert.rejects(load.execute('stopped',{names:['source_1']}),/closed/);
});

test('restoring a previously loaded tool never exceeds activation capacity',async()=>{
 for(const limits of [{maxActiveTools:1},{maxActiveSchemaChars:1200}]){
 const {controller:c,calls}=fixture(limits);const hooks=new Map();let active=[];
 c.configure({on:(n,f)=>hooks.set(n,f),getActiveTools:()=>active,setActiveTools:n=>active=n});
 await c.tools[1].execute('first',{names:['source_0']});hooks.get('turn_end')();
 await c.tools[1].execute('replace',{names:['source_1']});hooks.get('turn_end')();
 await assert.rejects(c.guardedTools.find(t=>t.name==='source_0').execute('blocked',{}),/capacity/);
 assert.equal(calls(),0);assert.deepEqual(active,['agent_tool_search','agent_tool_load','source_1']);
 }
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
  assert.equal(host.createApplicationToolDiscovery(config),undefined);
  config.applicationPolicy.allowed_tools.push('ungranted');
  assert.throws(()=>host.createApplicationToolDiscovery(config),/authorize/);
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

for(const mode of ['parent','managed-child'])test('actual pinned SDK '+mode+' invokes an admitted entry on its first turn and loads other exact contracts on demand',async()=>{
  assert.equal(typeof host.createApplicationToolDiscovery,'function');
  const sdk=await import('../../../../.grid-agent/runtime/pi/source/packages/coding-agent/dist/index.js');
  const ai=await import('../../../../.grid-agent/runtime/pi/source/packages/ai/dist/index.js');
  const dir=await mkdtemp(join(mode==='parent'?tmpdir():new URL('../../../../.grid-agent/runtime/',import.meta.url).pathname,'tool-discovery-sdk-'));
  const previousAgentDir=process.env.PI_CODING_AGENT_DIR;
  process.env.PI_CODING_AGENT_DIR=dir;
  const calls=[],menus=[],errors=[],observations=[],recoveries=[],capturedMenus=[];
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
    catalog:{revision:'revision',tools:publications,entry_tools:['data_gateway_source_28','data_gateway_source_29'],tool_hashes:Object.fromEntries(Object.keys(publications).map((name,i)=>[name,'hash-'+i]))}}};
  const discovery=host.createApplicationToolDiscovery(config);
  const model={id:'fixture',name:'Fixture',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',
    reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
  let index=0;
  const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
    streamSimple(_model,context){
      menus.push(context.tools.map(t=>({name:t.name,parameters:t.parameters})));
      recoveries.push(...context.messages.filter(message=>message.role==='toolResult'&&
        message.content?.some(part=>part.type==='text'&&part.text.includes('"code":"tool_not_active"'))));
      const batches=[
        [{name:'data_gateway_source_28',arguments:{query:'startup'}}],
        [{name:'agent_tool_load',arguments:{names:['source_0']}},
          {name:'data_gateway_source_0',arguments:{query:'too early'}}],
        [{name:'data_gateway_source_0',arguments:{query:'current'}}],
        [{name:'agent_tool_load',arguments:{names:['source_29']}}],
        [{name:'agent_tool_load',arguments:{names:[]}}],
        [{name:'data_gateway_source_0',arguments:{}}],
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
      owned=await host.createManagedChildSession(config,sdk,runtime,{cwd:dir,toolNames:['data_gateway_source_0','data_gateway_source_28']});
      session=owned.session;
    }else{
    const settingsManager=sdk.SettingsManager.inMemory({compaction:{enabled:false}});
    const loader=new sdk.DefaultResourceLoader({cwd:dir,agentDir:dir,settingsManager,noExtensions:true,noSkills:true,
      noPromptTemplates:true,noThemes:true,noContextFiles:true,agentsFilesOverride:()=>({agentsFiles:[]}),
      extensionFactories:[pi=>{discovery.configure(pi);pi.on('before_model_request',e=>capturedMenus.push(e.context.tools.map(t=>t.name)));}]});await loader.reload();
    ({session}=await sdk.createAgentSession({cwd:dir,agentDir:dir,modelRuntime:runtime,model,resourceLoader:loader,
      settingsManager,sessionManager:sdk.SessionManager.inMemory(),...host.applicationToolOptions(config,[],undefined,discovery)}));
    await session.bindExtensions({onError:error=>errors.push(error)});
    session.setActiveToolsByName(discovery.initialToolNames(config.applicationPolicy.allowed_tools));
    discovery.installSession(session);
    }
    session.subscribe(event=>{if(event.type==='tool_execution_end'&&event.toolName==='data_gateway_source_0'&&!event.isError)
      observations.push(host.rpcEvent(event));});
    await session.prompt('Read a published source.');
    assert.deepEqual(errors,[]);assert.equal(calls.length,3);assert.equal(calls[0].arguments.query,'startup');assert.equal(calls[1].arguments.query,'current');assert.equal(calls[2].arguments.query,'old menu');
    assert.ok(recoveries.length>0,'The real SDK model context must explain an inactive published tool');
    assert.deepEqual(menus[0].map(t=>t.name),['agent_tool_search','agent_tool_load','data_gateway_source_28']);
    assert.deepEqual(menus[1],menus[0]);
    assert.deepEqual(menus[2].find(t=>t.name==='data_gateway_source_0').parameters,publications.data_gateway_source_0.inputSchema);
    assert.ok(menus.every(menu=>menu.length<=4));
    assert.ok(menus.every(menu=>menu.some(t=>t.name==='data_gateway_source_28')));
    assert.ok(menus.every(menu=>!menu.some(t=>t.name==='data_gateway_source_29')));
    if(mode==='parent')assert.deepEqual(capturedMenus,menus.map(menu=>menu.map(t=>t.name)),
      'Canonical model-request capture must see the same bounded menu sent to the provider');
    const results=session.messages.filter(m=>m.role==='toolResult');
    assert.ok(results.some(m=>m.toolName==='agent_tool_load'&&m.isError));
    assert.ok(results.some(m=>m.toolName==='data_gateway_source_0'&&m.isError));
    assert.equal(results.filter(m=>m.toolName==='data_gateway_source_0'&&!m.isError).length,2);
    assert.ok(results.every(m=>!m.content?.some(p=>p.type==='text'&&/^Tool .* not found$/.test(p.text))));
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
