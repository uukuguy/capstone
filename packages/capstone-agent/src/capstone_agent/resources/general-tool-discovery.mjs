import {createHash} from 'node:crypto';
import {boundToolResult} from './tool-result-context.mjs';

export const discoveryToolNames=['agent_tool_search','agent_tool_load'];
const reply=value=>({content:[{type:'text',text:JSON.stringify(value)}]});

// This is a task-local index of an already admitted publication. Search and
// activation cannot refresh a catalog or extend the host's grant.
export function createToolDiscovery({tools,publications,contractHashes={},admittedNames,cwd,
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
  const searched=new Set();
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
      const searchKey=JSON.stringify([terms,offset]),repeated=searched.has(searchKey);
      if(searched.size>=64&&!repeated)searched.delete(searched.values().next().value);
      searched.add(searchKey);
      return reply({tools:selected.map(name=>({name,description:String(entries.get(name).publication.description??name).slice(0,maxSummaryChars),
        contract_sha256:entries.get(name).hash})),total:matches.length,
        next_offset:offset+selected.length<matches.length?offset+selected.length:null,
        ...(repeated?{discovery_feedback:{repeated_query:true,publication_changed:false,
          guidance:'This task publication is unchanged. Reuse these results and load the needed exact contracts. Change search terms or page only to investigate a different capability; a repeated search cannot refresh tools.'}}:{})});
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
      return boundToolResult(reply({activation:'next_turn',tools:contracts.map(({name,contract_sha256,publication})=>({name,contract_sha256,
        ...('outputSchema' in publication?{outputSchema:publication.outputSchema}:{})}))}),
        {cwd,toolName:'agent_tool_load',callId:_id});
    }};
  function close(){closed=true;active.clear();searched.clear();pending=undefined;}
  return {tools:[search,load],initialToolNames,close,
    admittedTools:[...entries.values()].map(({tool})=>tool),
    guardedTools:[...entries].map(([name,{tool}])=>({...tool,async execute(...args){
      check(args[2]);if(!active.has(name))throw new Error('Requested tool is not active; load it and wait for the next model turn');
      return tool.execute(...args);
    }})),
    configure(pi){
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
        '\nUse agent_tool_search for task-granted tool summaries and agent_tool_load for exact selected contracts; loaded tools become callable on the next model turn.'}));
      pi.on('turn_end',()=>{
        if(closed||!pending)return;
        active=new Set(pending);pending=undefined;
        pi.setActiveTools([...initialToolNames(pi.getActiveTools()),...active]);
      });
      pi.on('session_shutdown',close);
    }};
}
