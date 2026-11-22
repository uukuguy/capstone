/** Bounded operator view of SDK input. Omit reasoning and inline binary data. */
export function diagnosticContextInput(context,systemSources=[],toolSources,messageSources=[]) {
  const entries=[];
  let ordinal=0, remaining=400_000;
  function entry(carrier,role,body,source_id,name,origin) {
    ordinal++;
    if(entries.length>=256||remaining<=0)return;
    const serialized=typeof body==='string'?body:JSON.stringify(body);
    const limit=Math.min(remaining,48_000);
    const bytes=Buffer.from(serialized);
    const text=bytes.length<=limit?serialized:bytes.subarray(0,limit).toString('utf8');
    remaining-=Buffer.byteLength(text);
    entries.push({index:ordinal,carrier,role,text,truncated:bytes.length>limit,
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
  for(const message of context.messages??[]){
    const toolResult=message.role==='toolResult';
    const role=['user','assistant','toolResult'].includes(message.role)?message.role:'other';
    const carrier=toolResult?'tool_results':'messages';
    if(typeof message.content==='string'){
      entry(carrier,role,message.content,message.toolCallId,message.toolName);
      continue;
    }
    for(const part of Array.isArray(message.content)?message.content:[]){
      if(part.type==='thinking'||part.type==='redactedThinking')continue;
      if(part.type==='text'&&typeof part.text==='string'){
        const matchingSources=message.role==='user'?messageSources.filter(source=>source.timestamp===message.timestamp&&source.text===part.text):[];
        entry(carrier,role,part.text,message.toolCallId,message.toolName,matchingSources.length===1?matchingSources[0].origin:undefined);
      }
      else if(part.type==='toolCall')entry(carrier,'toolCall',{name:part.name,arguments:part.arguments},part.id,part.name);
      else entry(carrier,'unsupported',{type:typeof part.type==='string'?part.type:'unknown'},message.toolCallId);
    }
  }
  return {entries,total_entries:ordinal};
}
