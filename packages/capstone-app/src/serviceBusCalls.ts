export type ServiceBusCalls = {
  schema: 'capstone-service-bus-calls/1'; scope: 'current_tool_call'; reused: boolean
  attempt_count?: number; response_count?: number; transport_error_count?: number
  bus_declared_error_count?: number; observed_elapsed_ms?: number | null
  history_complete?: boolean; details_truncated?: boolean
  details: Record<string, string | number | boolean>[]
}
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
export function parseServiceBusCalls(value: unknown): ServiceBusCalls | undefined {
  if (!object(value) || value.schema !== 'capstone-service-bus-calls/1' || value.scope !== 'current_tool_call' || typeof value.reused !== 'boolean') return
  const result: ServiceBusCalls = {schema:value.schema,scope:value.scope,reused:value.reused,details:[]}
  for (const key of ['attempt_count','response_count','transport_error_count','bus_declared_error_count'] as const) {
    const count=value[key]
    if(typeof count==='number'&&Number.isSafeInteger(count)&&count>=0)result[key]=count
  }
  if(value.observed_elapsed_ms===null||typeof value.observed_elapsed_ms==='number'&&Number.isFinite(value.observed_elapsed_ms)&&value.observed_elapsed_ms>=0)result.observed_elapsed_ms=value.observed_elapsed_ms
  for(const key of ['history_complete','details_truncated'] as const)if(typeof value[key]==='boolean')result[key]=value[key]
  const strings=['call_id','request_id','span_id','service','method','table','query_class','status','started_at','finished_at','bus_response_code','bus_result','remote_execution']
  const numbers=['elapsed_ms','page_index','page_size','returned_records','reported_output_rows','response_body_bytes']
  if(Array.isArray(value.details))for(const raw of value.details.slice(-10)){
    if(!object(raw))continue
    const row:Record<string,string|number|boolean>={}
    for(const key of strings)if(typeof raw[key]==='string'&&raw[key].length<=256&&!/[\u0000-\u001f\u007f]/.test(raw[key]))row[key]=raw[key]
    for(const key of numbers)if(typeof raw[key]==='number'&&Number.isFinite(raw[key])&&raw[key]>=0)row[key]=raw[key]
    if(typeof raw.bridge_response_received==='boolean')row.bridge_response_received=raw.bridge_response_received
    result.details.push(row)
  }
  return result
}

/** One entry per host call. Replayed events and graph projections share its ID. */
export function serviceBusSummary(calls: readonly {id:string;serviceBusCalls?:ServiceBusCalls}[]) {
  const unique=new Map<string,ServiceBusCalls>()
  for(const call of calls)if(call.serviceBusCalls)unique.set(call.id,call.serviceBusCalls)
  const fresh=[...unique.values()].filter(call=>!call.reused)
  const reported=fresh.filter(call=>call.attempt_count!==undefined)
  const count=reported.reduce((sum,call)=>sum+call.attempt_count!,0)
  return {count:reported.length?count:undefined,unknown:fresh.length-reported.length,reused:unique.size-fresh.length}
}
