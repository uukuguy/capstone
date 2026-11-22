import {createHash} from 'node:crypto';

// Both extension and SDK loader execute in one isolated task process. The
// index is keyed by exact host-produced message content and metadata.
const originIndexKey=Symbol.for('capstone.diagnosticContextOrigins');
function messageKey(role,timestamp,text) {
  return createHash('sha256').update(JSON.stringify([role,timestamp,text])).digest('hex');
}
export function observeInjectedContext(message,origin) {
  if(typeof message.content!=='string')return;
  const index=globalThis[originIndexKey]??=new Map();
  const key=messageKey(message.role,message.timestamp,message.content);
  const prior=index.get(key);
  if(index.has(key)&&JSON.stringify(prior)!==JSON.stringify(origin)){index.set(key,null);return;}
  if(index.size<512)index.set(key,origin);
}
function injectedContextOrigin(message,text) {
  return globalThis[originIndexKey]?.get(messageKey(message.role,message.timestamp,text));
}

/** Bounded operator view of SDK input. Omit reasoning and inline binary data. */
export function diagnosticContextInput(context,systemSources=[],toolSources,messageSources=[]) {
  const entries=[];
  let ordinal=0, remaining=400_000;
  let message_index, block_index;
  function entry(carrier,role,body,source_id,name,origin) {
    ordinal++;
    if(entries.length>=256||remaining<=0)return;
    const serialized=typeof body==='string'?body:JSON.stringify(body);
    const limit=Math.min(remaining,48_000);
    const bytes=Buffer.from(serialized);
    const text=bytes.length<=limit?serialized:bytes.subarray(0,limit).toString('utf8');
    remaining-=Buffer.byteLength(text);
    entries.push({index:ordinal,carrier,role,text,truncated:bytes.length>limit,
      ...(message_index===undefined?{}:{message_index,block_index}),
      ...(typeof name==='string'&&/^[A-Za-z0-9_.:-]{1,128}$/.test(name)?{name}:{}),
      ...(typeof source_id==='string'&&/^[A-Za-z0-9_.:-]{1,128}$/.test(source_id)?{source_id}:{ }),
      ...(origin?{origin}:carrier==='tool_results'&&toolSources?.has(source_id)?{origin:toolSources.get(source_id)}:{})});
  }
  const prompt=context.systemPrompt;
  if(typeof prompt==='string'&&prompt){
    // SDK assembly may wrap or omit a source. Attribute only an exact, unique
    // contiguous span so diagnostics cannot attach a false origin.
    const spans=systemSources.flatMap(source=>{
      if(typeof source?.content!=='string'||!source.content)return [];
      const start=prompt.indexOf(source.content);
      if(start<0||prompt.indexOf(source.content,start+1)!==-1)return [];
      return [{start,end:start+source.content.length,source}];
    }).sort((left,right)=>left.start-right.start||right.end-left.end);
    let cursor=0;
    for(const {start,end,source} of spans){
      if(start<cursor)continue;
      if(start>cursor)entry('system','system',prompt.slice(cursor,start));
      entry('system','system',prompt.slice(start,end),source.id,source.name);
      cursor=end;
    }
    if(cursor<prompt.length)entry('system','system',prompt.slice(cursor));
  }
  for(const tool of context.tools??[]){
    entry('tools','definition',{name:tool.name,description:tool.description,parameters:tool.parameters},undefined,tool.name);
  }
  for(const [position,message] of (context.messages??[]).entries()){
    message_index=position+1;
    block_index=1;
    const toolResult=message.role==='toolResult';
    const role=['user','assistant','toolResult'].includes(message.role)?message.role:'other';
    const carrier=toolResult?'tool_results':'messages';
    if(typeof message.content==='string'){
      entry(carrier,role,message.content,message.toolCallId,message.toolName,injectedContextOrigin(message,message.content));
      continue;
    }
    for(const [position,part] of (Array.isArray(message.content)?message.content:[]).entries()){
      block_index=position+1;
      if(part.type==='thinking'||part.type==='redactedThinking')continue;
      if(part.type==='text'&&typeof part.text==='string'){
        const matchingSources=message.role==='user'?messageSources.filter(source=>source.timestamp===message.timestamp&&source.text===part.text):[];
        entry(carrier,role,part.text,message.toolCallId,message.toolName,matchingSources.length===1?matchingSources[0].origin:injectedContextOrigin(message,part.text));
      }
      else if(part.type==='toolCall')entry(carrier,'toolCall',{name:part.name,arguments:part.arguments},part.id,part.name);
      else entry(carrier,'unsupported',{type:typeof part.type==='string'?part.type:'unknown'},message.toolCallId);
    }
  }
  return {entries,total_entries:ordinal};
}
