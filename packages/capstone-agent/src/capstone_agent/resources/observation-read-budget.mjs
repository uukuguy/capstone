// Recovery uses the admitted reference and measured data, never source semantics.
export function observationReadBudgetError(value,{ref,pointer,maximumBytes,page}){
  const recovery={operation:'inspect',ref,pointer};
  if(Array.isArray(value)){
    const offset=page?.offset??0;
    let limit=Math.min(page?.limit??100,value.length-offset);
    while(limit>0){
      const end=Math.min(value.length,offset+limit);
      const result={items:value.slice(offset,end),offset,total_items:value.length,
        next_offset:end<value.length?end:null};
      if(Buffer.byteLength(JSON.stringify(result))<=maximumBytes){
        Object.assign(recovery,{operation:'read',page:{offset,limit}});
        break;
      }
      limit=Math.floor(limit/2);
    }
  }
  return Error(JSON.stringify({code:'observation_read_budget_exceeded',
    message:'Selected observation exceeds the read budget.',maximum_bytes:maximumBytes,
    recovery,instruction:recovery.operation==='read'
      ?'Use tools.read with the same ref, pointer and suggested page; continue using next_offset. No upstream call is needed.'
      :'Use tools.inspect on the same ref and pointer, then select a narrower field. No upstream call is needed.'}));
}
