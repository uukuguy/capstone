import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {boundToolResult} from './tool-result-context.mjs';
import {gatewayToolGroup,gatewayToolAccess,gatewayToolUseGuidance} from './gateway-tool-use.mjs';
import {createToolIdentityResolver} from './tool-identity.mjs';

export const discoveryToolNames=['agent_tool_search','agent_tool_load'];
const reply=value=>({content:[{type:'text',text:JSON.stringify(value)}]});
const defaults=JSON.parse(readFileSync(new URL('./application-capacity.json',import.meta.url),'utf8')).limits;

// This is a task-local index of an already admitted publication. Search and
// activation cannot refresh a catalog or extend the host's grant.
export function createToolDiscovery({tools,publications,contractHashes={},admittedNames,cwd,useLedger,initialNames=[],resolveContracts,
  maxActiveTools=defaults.tool_active_count,maxActiveSchemaChars=defaults.tool_schema_chars,
  pageSize=defaults.tool_search_page_items,maxSummaryChars=defaults.tool_summary_chars}={}) {
  for(const limit of [maxActiveTools,maxActiveSchemaChars,pageSize,maxSummaryChars])
    if(!Number.isSafeInteger(limit)||limit<=0)throw new Error('Invalid tool discovery capacity');
  const grants=new Set(admittedNames),allNames=new Set(tools.map(tool=>tool.name));
  const entries=new Map(tools.filter(tool=>grants.has(tool.name)).map(tool=>{
    const publication=structuredClone(publications[tool.name]);
    if(!publication||tool.name.length>256)throw new Error('Invalid tool discovery publication');
    const metadata=JSON.stringify(Object.fromEntries(['usage','metadata','_meta']
      .filter(key=>Object.hasOwn(publication,key)).map(key=>[key,publication[key]])));
    return [tool.name,{tool,publication,metadata,hash:contractHashes[tool.name]??
      createHash('sha256').update(JSON.stringify(publication)).digest('hex')}];
  }));
  const identities=createToolIdentityResolver(Object.fromEntries(
    [...entries].map(([name,entry])=>[name,entry.publication])));
  if(!Array.isArray(initialNames)||initialNames.some(name=>typeof name!=='string'))
    throw new Error('Invalid initial tool names');
  const initial=[...new Set(initialNames.filter(name=>entries.has(name)))];
  const capacity={max_tools:maxActiveTools,entry_tools:initial.length,selectable_tools:Math.max(0,maxActiveTools-initial.length)};
  function checkedContracts(selected){
    if(selected.length>maxActiveTools)throw new Error(`Tool activation count capacity exceeded: actual=${selected.length}; limit=${maxActiveTools}; entry_tools=${initial.length}; selectable_tools=${capacity.selectable_tools}. Select a smaller replacement set; no tools were activated.`);
    const contracts=selected.map(name=>({name,contract_sha256:entries.get(name).hash,publication:entries.get(name).publication}));
    // Only input contracts enter the model menu; output schemas stay in the
    // saved load result, without consuming input schema capacity.
    const actual=JSON.stringify(selected.map(name=>{const t=entries.get(name).tool;
      return {name,description:t.description??entries.get(name).publication.description,parameters:t.parameters??entries.get(name).publication.inputSchema};})).length;
    if(actual>maxActiveSchemaChars)throw new Error(`Tool activation schema capacity exceeded: actual=${actual}; limit=${maxActiveSchemaChars}; unit=characters. Select fewer input contracts; no tools were activated.`);
    return contracts;
  }
  checkedContracts(initial);
  const names=[...entries.keys()].sort();
  const groups=new Map();
  for(const name of names){
    const publication=entries.get(name).publication,id=gatewayToolGroup(publication);
    if(id){const group=groups.get(id)??{id,tool_count:0,access:gatewayToolAccess(publication)};group.tool_count++;groups.set(id,group);}
  }
  let active=new Set(initial),pending,closed=false;
  const learned=new Set(initial);
  let publishActivation,installedSession,restoreStream,extensionApi,wrapLoaded=tool=>tool;
  const dynamicRegistered=new Set();
  async function resolveSelected(names,signal){
    const missing=names.filter(name=>entries.get(name).publication.progressive&&!Object.hasOwn(entries.get(name).publication,'inputSchema'));
    if(!missing.length)return;
    if(!resolveContracts)throw Error('Exact selected contracts are unavailable');
    const resolved=await resolveContracts(missing,{signal});check(signal);
    for(const name of missing){
      const entry=entries.get(name),publication=resolved[name];
      if(!publication||!Object.hasOwn(publication,'inputSchema')||publication.name!==entry.publication.name||
          publication.progressive?.tool_contract_revision!==entry.publication.progressive?.tool_contract_revision)
        throw Error('Selected exact contract identity changed');
      entry.publication=publication;entry.tool.parameters=publication.inputSchema;
      if(extensionApi&&!dynamicRegistered.has(name)){
        extensionApi.registerTool(wrapLoaded(guarded(name,entry.tool)));dynamicRegistered.add(name);
      }
    }
  }
  const searched=new Set();
  function check(signal){signal?.throwIfAborted();if(closed)throw new Error('Tool discovery task is closed');}
  function initialToolNames(existingNames){
    return [...new Set([...existingNames.filter(name=>!allNames.has(name)),...discoveryToolNames,...initial])];
  }
  const search={name:'agent_tool_search',label:'Search admitted tools',
    description:'Search the task-granted published tool index only when the required tool is not already known. Results report activation and published toolset membership; optionally filter by a returned toolset ID. Exact published names take priority. If no tool matches all keywords, return the bounded best partial matches, marked partial_terms; these are candidates, not a semantic selection. Already active tools need no load. For composition, select known granted names and inspect tools.describe(name) without loading them into the direct-call menu. Follow current service selection and provider rules.',
    parameters:{type:'object',properties:{query:{type:'string',maxLength:256},toolset:{type:'string',minLength:1,maxLength:128},offset:{type:'integer',minimum:0}},required:['query'],additionalProperties:false},
    async execute(_id,args,signal){
      check(signal);
      if(typeof args.query!=='string'||args.query.length>256||!Number.isSafeInteger(args.offset??0)||(args.offset??0)<0)
        throw new Error('Invalid tool search arguments');
      if(args.toolset!==undefined&&(typeof args.toolset!=='string'||!args.toolset.length||args.toolset.length>128))throw new Error('Invalid toolset filter');
      const query=args.query.trim().toLowerCase(),terms=[...new Set(query.split(/\s+/).filter(Boolean))],offset=args.offset??0;
      const candidates=names.filter(name=>args.toolset===undefined||gatewayToolGroup(entries.get(name).publication)===args.toolset);
      const matched=new Map(candidates.map(name=>{
        const entry=entries.get(name),p=entry.publication,text=(name+' '+(p.name??'')+' '+(p.description??'')+' '+entry.metadata).toLowerCase();
        return [name,terms.filter(term=>text.includes(term))];
      }));
      const exact=query?candidates.filter(name=>[name,entries.get(name).publication.name].some(value=>typeof value==='string'&&value.toLowerCase()===query)):[];
      let mode=exact.length?'exact_name':'all_terms';
      let matches=exact.length?exact:candidates.filter(name=>matched.get(name).length===terms.length);
      if(!matches.length&&terms.length){
        const best=Math.max(0,...candidates.map(name=>matched.get(name).length));
        if(best){mode='partial_terms';matches=candidates.filter(name=>matched.get(name).length===best);}
      }
      const selected=matches.slice(offset,offset+pageSize);
      const searchKey=JSON.stringify([terms,offset,args.toolset??null]),repeated=searched.has(searchKey);
      if(searched.size>=64&&!repeated)searched.delete(searched.values().next().value);
      searched.add(searchKey);
      return reply({capacity,match_mode:mode,active_entry_tools:initial,toolsets:[...groups.values()],selection_guidance:gatewayToolUseGuidance,
        tools:selected.map(name=>({name,active:active.has(name),matched_terms:matched.get(name),toolset:gatewayToolGroup(entries.get(name).publication),access:gatewayToolAccess(entries.get(name).publication),description:String(entries.get(name).publication.description??name).slice(0,maxSummaryChars),
        ...(entries.get(name).metadata!=='{}'?{
          published_metadata_preview:entries.get(name).metadata.slice(0,maxSummaryChars),
          published_metadata_truncated:entries.get(name).metadata.length>maxSummaryChars}:{}),
        contract_sha256:entries.get(name).hash})),total:matches.length,
        next_offset:offset+selected.length<matches.length?offset+selected.length:null,
        ...(repeated?{discovery_feedback:{repeated_query:true,publication_changed:false,
          guidance:'This task publication is unchanged. Reuse these results and load the needed exact contracts. Change search terms or page only to investigate a different capability; a repeated search cannot refresh tools.'}}:{})});
    }};
  const load={name:'agent_tool_load',label:'Load admitted tools',
    description:`Select a bounded replacement set for direct model tool calls. Skip loading tools already active, or tools used only inside a composition program; composition accepts selected granted names and exposes tools.describe(name). Capacity: ${maxActiveTools} total, ${initial.length} retained entry tools, ${capacity.selectable_tools} additional distinct tools. Already active registered entry tools remain available and share capacity. Activation takes effect at the next model turn; do not invoke newly selected tools in this same call batch. Previously loaded contracts may be restored on later calls within the same capacity limits. Published schemas stay exact. Use an empty list to unload on-demand tools.`,
    parameters:{type:'object',properties:{names:{type:'array',items:{type:'string'},uniqueItems:true,maxItems:maxActiveTools}},required:['names'],additionalProperties:false},
    async execute(_id,args,signal){
      check(signal);
      let resolved;
      try{resolved=identities.resolveMany(args.names);}
      catch(error){throw new Error(error.message+'. No tools were activated.');}
      const selected=[...new Set([...initial,...resolved])];
      if(selected.length>maxActiveTools)checkedContracts(selected);
      await resolveSelected(selected,signal);
      const contracts=checkedContracts(selected);
      pending=selected;
      // Input schemas enter the next model menu; full output contracts are
      // available here without injecting the rest of the catalog.
      return boundToolResult({...reply({activation:'next_turn',name_resolutions:args.names.map((requested_name,i)=>({requested_name,name:resolved[i]})),selection_guidance:gatewayToolUseGuidance,tools:contracts.map(({name,contract_sha256,publication})=>({name,contract_sha256,
        ...('outputSchema' in publication?{outputSchema:publication.outputSchema}:{})}))})},
        {cwd,toolName:'agent_tool_load',callId:_id});
    }};
  function installSession(session){
    if(installedSession===session)return;
    if(installedSession)throw new Error('Tool discovery belongs to another session');
    check();
    installedSession=session;
    const visible=[...new Set([...initialToolNames(session.getActiveToolNames()),...active])];
    // Keep SDK dispatch definitions for granted tools without sending their
    // schemas to the model. Every definition still has the activation guard.
    session.setActiveToolsByName([...new Set([...visible,...entries.keys()])]);
    publishActivation=()=>{
      session.setActiveToolsByName([...new Set([...initialToolNames(session.getActiveToolNames()),
        ...[...entries].filter(([,entry])=>Object.hasOwn(entry.publication,'inputSchema')).map(([name])=>name)])]);
      const dispatch=session.agent.state.tools.slice();
      session.setActiveToolsByName([...new Set([...initialToolNames(session.getActiveToolNames()),...active])]);
      session.agent.state.tools=dispatch;
    };
    const original=session.agent.streamFunction;
    const projected=(model,context,options)=>original(model,{...context,
      tools:context.tools?.filter(tool=>!allNames.has(tool.name)||active.has(tool.name))},options);
    session.agent.streamFunction=projected;
    restoreStream=()=>{if(session.agent.streamFunction===projected)session.agent.streamFunction=original;};
    publishActivation();
  }
  function close(){closed=true;active.clear();learned.clear();searched.clear();pending=undefined;restoreStream?.();}
  function guarded(name,tool){return {...tool,async execute(...args){
    check(args[2]);
    if(!active.has(name)){
      if(!learned.has(name))throw Error(JSON.stringify({code:'tool_not_active',tool:name,executed:false,
        recovery:{tool:'agent_tool_load',arguments:{names:[name]},activation:'next_turn'}}));
      const restored=[...new Set([...active,name])];checkedContracts(restored);
      active=new Set(restored);publishActivation?.();
    }
    return tool.execute(...args);
  }};}
  return {tools:[search,load],initialToolNames,installSession,close,
    setLoadedWrapper:fn=>{wrapLoaded=fn;},
    admittedTools:[...entries.values()].map(({tool})=>tool),
    guardedTools:[...entries].filter(([,entry])=>!entry.publication.progressive||Object.hasOwn(entry.publication,'inputSchema')).map(([name,{tool}])=>({...tool,async execute(...args){
      check(args[2]);
      if(!active.has(name)){
        if(!learned.has(name))throw new Error(JSON.stringify({code:'tool_not_active',tool:name,
          message:'Tool is not active; load its exact contract and wait for the next model turn.',
          executed:false,recovery:{tool:'agent_tool_load',arguments:{names:[name]},activation:'next_turn'}}));
        const restored=[...new Set([...active,name])];
        // Restore a previously learned contract only within the same budgets.
        // A failed SDK lookup has not executed a remote call, so this is not a retry.
        try{checkedContracts(restored);}
        catch(error){throw new Error(JSON.stringify({code:'tool_activation_capacity',tool:name,
          message:error.message,executed:false,
          recovery:{tool:'agent_tool_load',arguments:{names:[name]},activation:'next_turn'}}));}
        active=new Set(restored);publishActivation?.();
      }
      return tool.execute(...args);
    }})),
    configure(pi){
      extensionApi=pi;
      publishActivation=()=>pi.setActiveTools([...new Set([...initialToolNames(pi.getActiveTools()),...active])]);
      pi.on('context',event=>{
        let changed=false;
        const messages=event.messages.map(message=>{
          const name=message.toolName;
          if(message.role!=='toolResult'||message.isError!==true||!entries.has(name)||active.has(name)||
            !message.content?.some(part=>part.type==='text'&&part.text===`Tool ${name} not found`))return message;
          const text=JSON.stringify({code:'tool_not_active',tool:name,publication_changed:false,
            active_tools:[...active],recovery:{tool:'agent_tool_load',arguments:{names:[name]},activation:'next_turn'},
            guidance:'The tool is granted but absent from the current active menu. Loading replaces that menu; select the other tools needed for this work in the same bounded load. Wait for the next turn before calling them. Do not repeat discovery or the inactive call to refresh the publication.'});
          if(message.content.some(part=>part.type==='text'&&part.text===text))return message;
          changed=true;return {...message,content:[...message.content,{type:'text',text}]};
        });
        return changed?{messages}:undefined;
      });
      pi.on('before_agent_start',event=>({systemPrompt:(event.systemPrompt??'')+
        '\nChoose tools and skills for the current instruction from its context, published descriptions and task grants. '+
        (initial.length?'Registered entry tools are already active: '+JSON.stringify(initial)+'. Availability does not require a call. Only after selecting this service as relevant, follow its initialization and discovery contract before its business operations. ':'')+
        'Search only when the needed tool is not known from the current menu or observed publication. Do not search an already known exact name just to confirm it. Load inactive tools only for direct model calls; newly loaded tools become callable on the next model turn. Composition programs select granted names independently of menu activation and inspect their exact contracts with tools.describe(name). Registered entry tools remain available across loads. '+gatewayToolUseGuidance}));
      pi.on('turn_end',()=>{
        if(closed||!pending)return;
        active=new Set(pending);pending=undefined;
        for(const name of active)learned.add(name);
        publishActivation();
      });
      pi.on('session_shutdown',close);
    }};
}
