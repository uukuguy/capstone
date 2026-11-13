import {expect,it} from 'vitest'
import {parseServiceBusCalls,serviceBusSummary} from './serviceBusCalls'
const raw={schema:'capstone-service-bus-calls/1',scope:'current_tool_call',reused:false,attempt_count:23,details_truncated:true,details:[{service:'query',sql:'private'}]}
it('keeps full counters while bounding details and dropping business fields',()=>{
 const value=parseServiceBusCalls(raw)!
 expect(value.attempt_count).toBe(23);expect(value.details).toEqual([{service:'query'}])
 expect(parseServiceBusCalls({...raw,scope:'job_business_fetch'})).toBeUndefined()
})
it('deduplicates records and excludes reused observations without turning unknown into zero',()=>{
 const a={id:'a',serviceBusCalls:parseServiceBusCalls(raw)}
 expect(serviceBusSummary([a,a,{id:'b',serviceBusCalls:parseServiceBusCalls({...raw,reused:true})}])).toEqual({count:23,unknown:0,reused:1})
 expect(serviceBusSummary([{id:'a',serviceBusCalls:parseServiceBusCalls({...raw,attempt_count:true})}])).toEqual({count:undefined,unknown:1,reused:0})
 expect(serviceBusSummary([{id:'a',serviceBusCalls:parseServiceBusCalls({...raw,attempt_count:0})}]).count).toBe(0)
})
