import {createHash} from 'node:crypto';

export const discoveryToolNames=['agent_tool_search','agent_tool_load'];
const reply=value=>({content:[{type:'text',text:JSON.stringify(value)}]});

// This is a task-local index of an already admitted publication. Search and
// activation cannot refresh a catalog or extend the host's grant.
export function createToolDiscovery({tools,publications,contractHashes={},admittedNames,
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
  const names=[...entries.keys()].sort();
  let active=new Set(),pending,closed=false;
  function check(signal){signal?.throwIfAborted();if(closed)throw new Error('Tool discovery task is closed');}
  function initialToolNames(existingNames){
    return [...new Set([...existingNames.filter(name=>!allNames.has(name)),...discoveryToolNames])];
  }
  const search={name:'agent_tool_search',label:'Search admitted tools',
    description:'Search the task-granted published tool index. Returns bounded summaries in pages; use agent_tool_load to activate selected exact contracts for the next model turn.',
    parameters:{type:'object',properties:{query:{type:'string',maxLength:256},offset:{type:'integer',minimum:0}},required:['query'],additionalProperties:false},
    async execute(_id,args,signal){
      check(signal);
      if(typeof args.query!=='string'||args.query.length>256||!Number.isSafeInteger(args.offset??0)||(args.offset??0)<0)
        throw new Error('Invalid tool search arguments');
      const terms=args.query.toLowerCase().split(/\s+/).filter(Boolean),offset=args.offset??0;
      const matches=names.filter(name=>{const text=(name+' '+(entries.get(name).publication.description??'')).toLowerCase();
        return terms.every(term=>text.includes(term));});
      const selected=matches.slice(offset,offset+pageSize);
      return reply({tools:selected.map(name=>({name,description:String(entries.get(name).publication.description??name).slice(0,maxSummaryChars),
        contract_sha256:entries.get(name).hash})),total:matches.length,
        next_offset:offset+selected.length<matches.length?offset+selected.length:null});
    }};
  const load={name:'agent_tool_load',label:'Load admitted tools',
    description:'Select a bounded replacement set of task-granted tools. Activation takes effect at the next model turn; do not invoke selected tools in this same call batch. Published schemas are kept exact. Use an empty list to unload them.',
    parameters:{type:'object',properties:{names:{type:'array',items:{type:'string'},uniqueItems:true,maxItems:maxActiveTools}},required:['names'],additionalProperties:false},
    async execute(_id,args,signal){
      check(signal);
      if(!Array.isArray(args.names)||args.names.some(name=>typeof name!=='string'||!entries.has(name)))
        throw new Error('Requested tool is not admitted for this task');
      const selected=[...new Set(args.names)];
      if(selected.length>maxActiveTools)throw new Error('Tool activation count capacity exceeded');
      const contracts=selected.map(name=>({name,contract_sha256:entries.get(name).hash,publication:entries.get(name).publication}));
      if(JSON.stringify(contracts).length>maxActiveSchemaChars)throw new Error('Tool activation schema capacity exceeded; select fewer tools');
      pending=selected;
      // Input schemas enter the next model menu; full output contracts are
      // available here without injecting the rest of the catalog.
      return reply({activation:'next_turn',tools:contracts.map(({name,contract_sha256,publication})=>({name,contract_sha256,
        ...('outputSchema' in publication?{outputSchema:publication.outputSchema}:{})}))});
    }};
  function close(){closed=true;active.clear();pending=undefined;}
  return {tools:[search,load],initialToolNames,close,
    guardedTools:[...entries].map(([name,{tool}])=>({...tool,async execute(...args){
      check(args[2]);if(!active.has(name))throw new Error('Requested tool is not active; load it and wait for the next model turn');
      return tool.execute(...args);
    }})),
    configure(pi){
      pi.on('before_agent_start',event=>({systemPrompt:(event.systemPrompt??'')+
        '\nUse agent_tool_search for task-granted tool summaries and agent_tool_load for exact selected contracts; loaded tools become callable on the next model turn.'}));
      pi.on('turn_end',()=>{
        if(closed||!pending)return;
        active=new Set(pending);pending=undefined;
        pi.setActiveTools([...initialToolNames(pi.getActiveTools()),...active]);
      });
      pi.on('session_shutdown',close);
    }};
}
