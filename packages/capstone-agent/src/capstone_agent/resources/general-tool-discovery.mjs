import {createHash} from 'node:crypto';
import {boundToolResult} from './tool-result-context.mjs';
import {gatewayToolGroup,gatewayToolAccess,gatewayToolUseGuidance} from './gateway-tool-use.mjs';
import {createToolIdentityResolver} from './tool-identity.mjs';

export const discoveryToolNames=['agent_tool_search','agent_tool_load'];
const reply=value=>({content:[{type:'text',text:JSON.stringify(value)}]});

// This is a task-local index of an already admitted publication. Search and
// activation cannot refresh a catalog or extend the host's grant.
export function createToolDiscovery({tools,publications,contractHashes={},admittedNames,cwd,useLedger,initialNames=[],
  maxActiveTools=8,maxActiveSchemaChars=24000,pageSize=8,maxSummaryChars=240}={}) {
  for(const limit of [maxActiveTools,maxActiveSchemaChars,pageSize,maxSummaryChars])
    if(!Number.isSafeInteger(limit)||limit<=0)throw new Error('Invalid tool discovery capacity');
  const grants=new Set(admittedNames),allNames=new Set(tools.map(tool=>tool.name));
  const entries=new Map(tools.filter(tool=>grants.has(tool.name)).map(tool=>{
    const publication=structuredClone(publications[tool.name]);
    if(!publication||tool.name.length>256)throw new Error('Invalid tool discovery publication');
    return [tool.name,{tool,publication,hash:contractHashes[tool.name]??
      createHash('sha256').update(JSON.stringify(publication)).digest('hex')}];
  }));
  const identities=createToolIdentityResolver(Object.fromEntries(
    [...entries].map(([name,entry])=>[name,entry.publication])));
  if(!Array.isArray(initialNames)||initialNames.some(name=>typeof name!=='string'))
    throw new Error('Invalid initial tool names');
  const initial=[...new Set(initialNames.filter(name=>entries.has(name)))];
  function checkedContracts(selected){
    if(selected.length>maxActiveTools)throw new Error('Tool activation count capacity exceeded');
    const contracts=selected.map(name=>({name,contract_sha256:entries.get(name).hash,publication:entries.get(name).publication}));
    if(JSON.stringify(contracts).length>maxActiveSchemaChars)throw new Error('Tool activation schema capacity exceeded; select fewer tools');
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
  let publishActivation,installedSession,restoreStream;
  const searched=new Set();
  function check(signal){signal?.throwIfAborted();if(closed)throw new Error('Tool discovery task is closed');}
  function initialToolNames(existingNames){
    return [...new Set([...existingNames.filter(name=>!allNames.has(name)),...discoveryToolNames,...initial])];
  }
  const search={name:'agent_tool_search',label:'Search admitted tools',
    description:'Search the task-granted published tool index. Results include published toolset membership; optionally filter by a returned toolset ID. Follow selection and provider rules returned by current gateway discovery. Load selected exact contracts for the next model turn.',
    parameters:{type:'object',properties:{query:{type:'string',maxLength:256},toolset:{type:'string',minLength:1,maxLength:128},offset:{type:'integer',minimum:0}},required:['query'],additionalProperties:false},
    async execute(_id,args,signal){
      check(signal);
      if(typeof args.query!=='string'||args.query.length>256||!Number.isSafeInteger(args.offset??0)||(args.offset??0)<0)
        throw new Error('Invalid tool search arguments');
      if(args.toolset!==undefined&&(typeof args.toolset!=='string'||!args.toolset.length||args.toolset.length>128))throw new Error('Invalid toolset filter');
      const terms=args.query.toLowerCase().split(/\s+/).filter(Boolean),offset=args.offset??0;
      const matches=names.filter(name=>{const text=(name+' '+(entries.get(name).publication.description??'')).toLowerCase();
        return (args.toolset===undefined||gatewayToolGroup(entries.get(name).publication)===args.toolset)&&terms.every(term=>text.includes(term));});
      const selected=matches.slice(offset,offset+pageSize);
      const searchKey=JSON.stringify([terms,offset,args.toolset??null]),repeated=searched.has(searchKey);
      if(searched.size>=64&&!repeated)searched.delete(searched.values().next().value);
      searched.add(searchKey);
      return reply({toolsets:[...groups.values()],selection_guidance:gatewayToolUseGuidance,
        tools:selected.map(name=>({name,toolset:gatewayToolGroup(entries.get(name).publication),access:gatewayToolAccess(entries.get(name).publication),description:String(entries.get(name).publication.description??name).slice(0,maxSummaryChars),
        contract_sha256:entries.get(name).hash})),total:matches.length,
        next_offset:offset+selected.length<matches.length?offset+selected.length:null,
        ...(repeated?{discovery_feedback:{repeated_query:true,publication_changed:false,
          guidance:'This task publication is unchanged. Reuse these results and load the needed exact contracts. Change search terms or page only to investigate a different capability; a repeated search cannot refresh tools.'}}:{})});
    }};
  const load={name:'agent_tool_load',label:'Load admitted tools',
    description:'Select a bounded replacement set of on-demand task-granted tools. Already active registered entry tools remain available and share capacity. Activation takes effect at the next model turn; do not invoke newly selected tools in this same call batch. Previously loaded contracts may be restored on later calls within the same capacity limits. Published schemas stay exact. Use an empty list to unload on-demand tools.',
    parameters:{type:'object',properties:{names:{type:'array',items:{type:'string'},uniqueItems:true,maxItems:maxActiveTools}},required:['names'],additionalProperties:false},
    async execute(_id,args,signal){
      check(signal);
      let resolved;
      try{resolved=identities.resolveMany(args.names);}
      catch(error){throw new Error(error.message+'. No tools were activated.');}
      const selected=[...new Set([...initial,...resolved])];
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
    const dispatch=session.agent.state.tools.slice();
    publishActivation=()=>{
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
  return {tools:[search,load],initialToolNames,installSession,close,
    admittedTools:[...entries.values()].map(({tool})=>tool),
    guardedTools:[...entries].map(([name,{tool}])=>({...tool,async execute(...args){
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
        'For on-demand tools of a capability you selected, use agent_tool_search for task-granted summaries and agent_tool_load for exact contracts; newly loaded tools become callable on the next model turn. Registered entry tools remain available across loads. '+gatewayToolUseGuidance}));
      pi.on('turn_end',()=>{
        if(closed||!pending)return;
        active=new Set(pending);pending=undefined;
        for(const name of active)learned.add(name);
        publishActivation();
      });
      pi.on('session_shutdown',close);
    }};
}
