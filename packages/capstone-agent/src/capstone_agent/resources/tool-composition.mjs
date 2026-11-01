import {fork} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {randomUUID,createHash} from 'node:crypto';
import {saveSemanticContext,loadSemanticContext} from './semantic-data-context.mjs';
import {boundToolResult,readSavedObservation} from './tool-result-context.mjs';
import {gatewayToolUseGuidance} from './gateway-tool-use.mjs';
import {createToolIdentityResolver} from './tool-identity.mjs';
import {observedAction,readObservation} from './observed-action.mjs';
import {setTimeout as wait} from 'node:timers/promises';
export const compositionPolicy=Object.freeze(JSON.parse(readFileSync(new URL('./tool-composition-policy.json',import.meta.url),'utf8')));
const canonical=(v)=>Array.isArray(v)?v.map(canonical):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])])):v;
export function createToolCompositionTool({policy=compositionPolicy,cwd,catalog,admittedNames=Object.keys(catalog.tools),invoke,scope,useLedger,deadlineAt=Infinity,allowedInputs=[],restore=async x=>x,onProgress=()=>{}}){
  // Session-local issued observations survive program calls, never task grants.
  // A different DR node must receive an explicit saved context package.
  const records=new Map();
  // Only explicit non-correctable, unexecuted rejections persist across programs.
  // Transient timeouts retain their existing per-program policy.
  const rejectedRequests=new Map();
  const identities=createToolIdentityResolver(catalog.tools,admittedNames);
  return {name:'agent_tools_execute',label:'执行多步数据处理',description:'Run an async JavaScript program in the isolated task workspace. Select admitted gateway tools explicitly. For a known independent call list use tools.batch([{tool,arguments},...]): the host checks the whole batch against remaining capacity and selected tool identities before any call, reserves capacity, and runs it with bounded concurrency in input order. Per-call argument validation still applies; batch execution is not transactional. Use tools.call for dependent calls. tools.call(name,args) returns {ref,ok,status,data,provenance,gaps,value}; tools.describe(name) returns its exact contract. tools.follow(ref,pointer) executes an action copied from a successful host observation at that JSON pointer, preserving exact tool names and arguments. Select its target tool in tools first. Prefer follow for returned actions instead of retyping identifiers; it honors returned waits and uses the same grant/schema checks. python(code,data) runs Python with JSON stdin. saveContext(name,{bindings,datasets}) preserves observed source fields with call refs and JSON pointers, declared values, and unknown fields. loadContext(path) reuses a saved package. Return a compact summary; retain source data in packages. No automatic retries. Failed programs return completed_calls references when calls already finished; reuse them rather than reading again. Source packages are observations, not Authority evidence. tools.read(ref,pointer) reads a bounded exact field from a previous observation, including failed results, without another upstream call. For blocked repeats inspect previous_call; do not recreate an unchanged rejected request. '+`Limits for this instance: max_calls=${policy.max_calls}, concurrency=${policy.concurrency}, program_chars=${policy.code_chars}. Plan batches within these limits before writing a long program. `+gatewayToolUseGuidance,
    parameters:{type:'object',properties:{program:{type:'string',description:"Async program body. Example: const r=await tools.call(name,args); const saved=await saveContext('shared',{bindings:{unit:{call:r.ref,pointer:'/data/unit'},method:{value:'mean'},missing:{unknown:true,reason:'not provided'}},datasets:[{name:'load',call:r.ref,pointer:'/data/rows'}]}); return saved; Use actual returned fields in pointers. loadContext(saved.path) returns bindings with basis/value and datasets keyed by name with data/status/provenance/gaps. Plain binding values are declared metadata, never verified facts. Actual call refs remain usable by later programs in this instruction/session; different tasks need explicit saved packages. Large returns are saved automatically; return selected fields to reduce model context."},tools:{type:'array',items:{type:'string'}},purpose:{type:'string'},concurrency:{type:'integer',minimum:1,maximum:policy.concurrency},max_calls:{type:'integer',minimum:1,maximum:policy.max_calls},timeout_ms:{type:'integer',minimum:1,maximum:policy.max_program_ms}},required:['program','tools'],additionalProperties:false},
    async execute(callId,input,signal){
      signal?.throwIfAborted();
      const completedCalls=[];
      const batches=new Map();
      const failure=error=>({isError:true,content:[{type:'text',text:completedCalls.length?JSON.stringify({
        code:'composition_failed',message:String(error.message??error),completed_calls:completedCalls.slice(-8),
        completed_call_count:completedCalls.length,recovery:'Completed calls were not rolled back. Reuse their observation refs in this task; do not repeat them implicitly.'
      }):String(error.message??error)}]});
      let child,timer;const abort=new AbortController(),queue=[],operations=new Set(),resourceFailures=new Map(),blocked=new Map();let active=0,calls=0,requests=0,skipped=0,finished=false;
      const stop=()=>{abort.abort(Error('Composition stopped'));for(const reject of queue.splice(0))reject();if(child?.pid){try{process.kill(-child.pid,'SIGKILL');}catch{child.kill('SIGKILL');}}};
      try{
        if(typeof input.program!=='string'||input.program.length>policy.code_chars)throw Error('Program code budget exceeded');
        const selected=[...new Set(identities.resolveMany(input.tools))];
        const limit=input.max_calls??policy.max_calls,concurrency=input.concurrency??policy.concurrency;
        if(!Number.isInteger(limit)||limit<1||limit>policy.max_calls||!Number.isInteger(concurrency)||concurrency<1||concurrency>policy.concurrency)throw Error('Invalid composition limits');
        const timeout=Math.min(input.timeout_ms??policy.max_program_ms,policy.max_program_ms,deadlineAt-Date.now());
        if(!Number.isFinite(timeout)||timeout<=0)throw Error('Composition timeout');
        const run=randomUUID(),schemas=Object.fromEntries(selected.map(name=>[name,catalog.tools[name]]));
        const programIdentities=createToolIdentityResolver(schemas);
        const env=Object.fromEntries(['PATH','LANG','LC_ALL','TMPDIR'].filter(k=>process.env[k]).map(k=>[k,process.env[k]]));
        child=fork(new URL('./tool-composition-worker.mjs',import.meta.url),[],{cwd,env,detached:true,execArgv:[`--max-old-space-size=${policy.worker_memory_mb}`],stdio:['ignore','ignore','ignore','ipc']});
        const result=await new Promise((resolve,reject)=>{
          const cancel=()=>reject(signal.reason??Error('Composition aborted'));
          signal?.addEventListener('abort',cancel,{once:true});
          const settle=(value,error)=>{if(finished)return;finished=true;signal?.removeEventListener('abort',cancel);error?reject(error):resolve(value);};
          timer=setTimeout(()=>settle(undefined,Error('Composition timeout')),timeout);
          child.on('error',error=>settle(undefined,error));
          child.on('exit',(code,sig)=>settle(undefined,Error(`Composition worker exited (${code??sig})`)));
          const handleMessage=async message=>{
            if(finished)return;
            if(message.kind==='done'){settle(message.value,active||queue.length?Error('Program returned before pending calls finished'):undefined);return;}
            if(message.kind==='failed'){settle(undefined,Error(message.error));return;}
            let value,error;
            try{
              if(message.kind==='preflight'){
                const plan=message.calls,errors=[];
                if(!Array.isArray(plan)||!plan.length||plan.length>limit-requests)
                  throw Error(`Batch preflight: expected 1..${limit-requests} calls; no calls from this batch executed`);
                const prepared=plan.map((item,index)=>{
                  try{
                    if(!item||typeof item!=='object'||Object.keys(item).some(k=>!['tool','arguments'].includes(k))||
                        !item.arguments||typeof item.arguments!=='object'||Array.isArray(item.arguments))
                      throw Error('expected {tool,arguments:object}');
                    return {name:programIdentities.resolve(item.tool),args:structuredClone(item.arguments)};
                  }catch(e){errors.push({index,message:String(e.message??e)});return null;}
                });
                if(errors.length)throw Error('Batch preflight: no calls from this batch executed; '+JSON.stringify(errors));
                // Reserve the entire batch before releasing a single call.
                requests+=prepared.length;
                const ref=randomUUID();batches.set(ref,prepared);value={ref,count:prepared.length};
              }else{
              if(message.kind==='follow'){
                const action=observedAction(records,message.ref,message.pointer);
                // No replacement arguments cross the worker boundary.
                message={...message,kind:'call',...action};
              }
              if(message.kind==='call'){
                if(message.batchRef!==undefined){
                  const batch=batches.get(message.batchRef),item=Number.isInteger(message.index)?batch?.[message.index]:null;
                  if(!item)throw Error('Unknown or consumed batch call');
                  batch[message.index]=null;
                  message={...message,...item};
                }else{
                  message={...message,name:programIdentities.resolve(message.name)};
                  if(++requests>limit)throw Error('Composition call budget exceeded');
                }
                const argumentsHash=createHash('sha256').update(JSON.stringify(canonical(message.args))).digest('hex');
                const failureKey=message.name+':'+argumentsHash;
                if(active>=concurrency)await new Promise((resolve,reject)=>queue.push(()=>abort.signal.aborted?reject(abort.signal.reason):resolve()));
                abort.signal.throwIfAborted();active++;
                try{
                  if(rejectedRequests.has(failureKey)){
                    const previous=rejectedRequests.get(failureKey);
                    skipped++;value={ref:null,ok:false,status:'not_executed',data:null,
                      previous_call:previous.ref,gaps:previous.gaps,
                      recovery:'This exact request was already rejected as unexecuted and non-correctable. Inspect the previous observation; no new upstream call was made.',value:null};
                  }else if(blocked.has(failureKey)){
                    skipped++;value={ref:null,ok:false,status:'not_executed',data:null,gaps:[{reason:'repeated_resource_failure',tool:message.name,arguments_sha256:argumentsHash,scope:'unchanged_inputs'}],value:null};
                  }else{
                  calls++;
                  if(message.waitMs)await wait(message.waitMs,undefined,{signal:abort.signal});
                  const nestedId=`${callId}:${run}:${message.id}`,native=await restore(await invoke(message.name,message.args,{callId:nestedId,signal:abort.signal}));
                  let raw;try{raw=JSON.parse(native.content.find(c=>c.type==='text')?.text??'null');}catch{raw={text:native.content};}
                  const observed=raw?.structuredContent??raw;
                  const ref=`program-call:${run}:${message.id}`;
                  if(native.details?.kind==='external_gateway_observation')useLedger?.record(message.name,ref);
                  const ok=native.isError!==true&&!['error','failed','denied'].includes(observed?.status);
                  const timeout=!ok&&Array.isArray(observed?.gaps)&&observed.gaps.some(g=>/^(?:query_timeout|timeout|resource_exhausted|rate_limit)$/.test(g?.reason??''));
                  const count=timeout?(resourceFailures.get(failureKey)??0)+1:0;
                  resourceFailures.set(failureKey,count);
                  if(count>=policy.consecutive_resource_failures)blocked.set(failureKey,{tool:message.name,arguments_sha256:argumentsHash,scope:'unchanged_inputs'});
                  records.set(ref,{ref,ok,value:observed,receipt:native.details??{},observedAt:Date.now()});
                  if(!ok&&Array.isArray(observed?.gaps)&&observed.gaps.some(g=>g?.scope?.executed===false&&g.scope.correctable===false))
                    rejectedRequests.set(failureKey,{ref,gaps:structuredClone(observed.gaps)});
                  completedCalls.push({ref,tool:message.name,ok});
                  value={ref,ok,...(observed&&typeof observed==='object'?observed:{}),value:observed};
                  }
                }finally{active--;queue.shift()?.();}
              }else if(message.kind==='read'){
                value=typeof message.ref==='string'?readObservation(records,message.ref,message.pointer):
                  await readSavedObservation(message.ref,message.pointer,{cwd});
                if(message.page!==undefined){
                  const page=message.page;
                  if(!page||typeof page!=='object'||Array.isArray(page)||Object.keys(page).some(k=>!['offset','limit'].includes(k))||
                      !Number.isSafeInteger(page.offset)||page.offset<0||!Number.isSafeInteger(page.limit)||page.limit<1||!Array.isArray(value))
                    throw Error('/page: expected {offset:nonnegative integer,limit:positive integer} for an array');
                  const end=Math.min(value.length,page.offset+page.limit);
                  value={items:value.slice(page.offset,end),offset:page.offset,total_items:value.length,next_offset:end<value.length?end:null};
                }
                if(Buffer.byteLength(JSON.stringify(value))>policy.output_bytes)
                  throw Error('/pointer: Selected observation exceeds the read budget; select a narrower field or use saveContext for datasets');
              }else if(message.kind==='save')value=await saveSemanticContext({cwd,name:message.name,spec:message.spec,records,scope});
              else if(message.kind==='load')value=await loadSemanticContext({cwd,path:message.path,allowedInputs});
              else if(message.kind==='print'){value=undefined;onProgress(String(message.text).slice(0,policy.output_bytes));}
              else throw Error('Unknown composition request');
              }
            }catch(e){error=String(e.message??e);}
            if(!finished&&child.connected)child.send({kind:'reply',id:message.id,value,error});
          };
          child.on('message',message=>{
            const operation=handleMessage(message);operations.add(operation);
            operation.then(()=>operations.delete(operation),error=>{operations.delete(operation);settle(undefined,error);});
          });
          child.send({kind:'start',program:input.program,schemas,outputBytes:policy.output_bytes});
        });
        const text=JSON.stringify({result:result??null,calls,skipped_calls:skipped,limited_conditions:[...blocked.values()]});
        const bounded=await boundToolResult({isError:false,content:[{type:'text',text}],details:{kind:policy.schema,calls}},
          {cwd,toolName:'agent_tools_execute',callId,maxChars:policy.output_bytes});
        // Unlike gateway receipts, the program return has no host requirement
        // to inline original bytes. Keep the saved-file reference bounded even
        // when rpcEvent restores real upstream gateway observations.
        return {isError:bounded.isError,content:bounded.content,details:bounded.details};
      }catch(error){if(signal?.aborted)throw signal.reason??error;return failure(error);}
      finally{clearTimeout(timer);stop();await Promise.allSettled([...operations]);}
    }};
}
