/** Volatile stream content. This has no ledger identity or replay cursor. */
export type ThinkingPreview = {thread_id:string;attempt_id:string;batch_id:string;text:string;created_at:string;payload?:Record<string,string|number>}

export function parseThinkingPreview(value:unknown,threadId:string):ThinkingPreview {
  const row=value as Record<string,unknown>|null
  if(!row||typeof row!=='object'||Array.isArray(row)||row.thread_id!==threadId||
    ['thread_id','attempt_id','batch_id','text','created_at'].some(key=>typeof row[key]!=='string'||!(row[key] as string).length)||
    !Number.isFinite(Date.parse(row.created_at as string))||'event_seq' in row||
    (row.text as string).length>65536||(row.attempt_id as string).length>128||(row.batch_id as string).length>128)throw new Error('Thinking preview is invalid')
  const metadata:Record<string,string|number>={}
  if(row.payload&&typeof row.payload==='object'&&!Array.isArray(row.payload))for(const [key,value] of Object.entries(row.payload)){
    if(['task_id','task_step_id','task_step_number','runtime_mode','step_id','trace_correlation_id','trace_sequence','correlation_id'].includes(key)&&
      ((typeof value==='string'&&value.length<=256)||(typeof value==='number'&&Number.isSafeInteger(value))))metadata[key]=value
  }
  return {thread_id:row.thread_id as string,attempt_id:row.attempt_id as string,batch_id:row.batch_id as string,text:row.text as string,created_at:row.created_at as string,...(Object.keys(metadata).length?{payload:metadata}:{})}
}
