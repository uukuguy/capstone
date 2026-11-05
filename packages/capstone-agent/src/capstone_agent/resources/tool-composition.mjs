import {fork} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {randomUUID,createHash} from 'node:crypto';
import {saveSemanticContext,loadSemanticContext} from './semantic-data-context.mjs';
import {boundToolResult,savedToolObservation,readSavedObservation,structureIndex,resolveTaskObservation} from './tool-result-context.mjs';
import {gatewayToolUseGuidance} from './gateway-tool-use.mjs';
import {createToolIdentityResolver} from './tool-identity.mjs';
import {observedAction,readObservation} from './observed-action.mjs';
import {observationReadBudgetError} from './observation-read-budget.mjs';
import {setTimeout as wait} from 'node:timers/promises';
import {prepareObservationTable} from './observation-data.mjs';
export const compositionPolicy=Object.freeze(JSON.parse(readFileSync(new URL('./tool-composition-policy.json',import.meta.url),'utf8')));
const canonical=(v)=>Array.isArray(v)?v.map(canonical):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])])):v;
function refreshReason(options){
  if(options===undefined)return undefined;
  if(!options||typeof options!=='object'||Array.isArray(options)||Object.keys(options).some(k=>!['refresh_reason','purpose','output','basis_refs'].includes(k))||
      options.refresh_reason!==undefined&&(typeof options.refresh_reason!=='string'||!options.refresh_reason.trim()||options.refresh_reason.length>512))
    throw Error('/options: expected refresh_reason and/or a retrieval plan {purpose,output,basis_refs}');
  if(['purpose','output','basis_refs'].some(k=>Object.hasOwn(options,k))&&
      (['purpose','output'].some(k=>typeof options[k]!=='string'||!options[k].trim()||options[k].length>1024)||
       !Array.isArray(options.basis_refs)||options.basis_refs.some(ref=>typeof ref!=='string'||!ref)))
    throw Error('/options: retrieval plan needs purpose, output and issued basis_refs');
  return options.refresh_reason;
}
export function createToolCompositionTool({policy=compositionPolicy,cwd,catalog,admittedNames=Object.keys(catalog.tools),invoke,validateCalls,scope,useLedger,deadlineAt=Infinity,allowedInputs=[],restore=async x=>x,onProgress=()=>{},reuseEligible=(schema)=>schema?.annotations?.readOnlyHint===true&&schema?.annotations?.idempotentHint===true&&schema?.annotations?.destructiveHint!==true}){
  // Session-local issued observations survive program calls, never task grants.
  // A different DR node must receive an explicit saved context package.
  const records=new Map();
  const successfulRequests=new Map(),inFlight=new Map();
  const resolveRecord=ref=>resolveTaskObservation(records,ref,{cwd,useLedger});
  const sourceRecords=async ref=>new Map([[ref,await resolveRecord(ref)]]);
  // Only explicit non-correctable, unexecuted rejections persist across programs.
  // Transient timeouts retain their existing per-program policy.
  const rejectedRequests=new Map();
  const identities=createToolIdentityResolver(catalog.tools,admittedNames);
  return {name:'agent_tools_execute',label:'执行多步数据处理',description:'Process source observations through one pipeline: tools.plan checks retrieval, tools.batch/call obtains or reuses results, tools.inspect/read finds exact fields, and tools.table validates and exports CSV. Prefer these helpers over shell exploration of saved JSON. Run the async JavaScript program in the isolated task workspace. Select admitted gateway tools explicitly. For a known independent call list use tools.batch([{tool,arguments},...]): the host checks the whole batch against remaining capacity, selected tool identities and frozen input schemas before any call, reserves capacity, and runs it with bounded concurrency in input order. Any invalid input rejects the entire batch before invocation. Per-call validation still applies; batch execution is not transactional. Use tools.call for dependent calls. tools.call(name,args) returns {ref,ok,status,data,provenance,gaps,value}; tools.describe(name) returns its exact contract. tools.follow(ref,pointer) executes an action copied from a successful host observation at that JSON pointer, preserving exact tool names and arguments. Select its target tool in tools first. Prefer follow for returned actions instead of retyping identifiers; it honors returned waits and uses the same grant/schema checks. python(code,data) runs Python with JSON stdin. saveContext(name,{bindings,datasets}) preserves observed source fields with call refs and JSON pointers, declared values, and unknown fields. loadContext(path) reuses a saved package. Return a compact summary; retain source data in packages. No automatic retries. Failed programs retain all completed_calls references; large manifests have an issued full_result readable with tools.read(full_result,"/completed_calls",{offset,limit}). Reuse completed results rather than reading again. A successful program also reports failed_call_count and failed_calls; do not confuse program completion with business success. Source packages are observations, not Authority evidence. tools.inspect(ref,pointer="") returns a bounded structure index without data values; use it and read in the same program instead of extra shell/model turns. tools.read returns the selected field directly, not a value wrapper; with an array page {offset,limit} it returns {items,total_items,next_offset,offset}. tools.read(ref,pointer) reads a bounded exact field from a previous observation, including failed results, without another upstream call. For blocked repeats inspect previous_call; do not recreate an unchanged rejected request. '+`Limits for this instance: max_calls=${policy.max_calls}, concurrency=${policy.concurrency}, program_chars=${policy.code_chars}. Plan batches within these limits before writing a long program. `+gatewayToolUseGuidance,
    parameters:{type:'object',properties:{program:{type:'string',description:"Async program body. Example: const r=await tools.call(name,args); const saved=await saveContext('shared',{bindings:{unit:{call:r.ref,pointer:'/data/unit'},method:{value:'mean'},missing:{unknown:true,reason:'not provided'}},datasets:[{name:'load',call:r.ref,pointer:'/data/rows'}]}); return saved; Use actual returned fields in pointers. loadContext(saved.path) returns bindings with basis/value and datasets keyed by name with data/status/provenance/gaps. Plain binding values are declared metadata, never verified facts. Actual call refs remain usable by later programs in this instruction/session; different tasks need explicit saved packages. Large returns are saved automatically; return selected fields to reduce model context."},tools:{type:'array',items:{type:'string'}},purpose:{type:'string'},concurrency:{type:'integer',minimum:1,maximum:policy.concurrency},max_calls:{type:'integer',minimum:1,maximum:policy.max_calls},timeout_ms:{type:'integer',minimum:1,maximum:policy.max_program_ms}},required:['program','tools'],additionalProperties:false},
    async execute(callId,input,signal){
      signal?.throwIfAborted();
      const completedCalls=[];
      const batches=new Map();
      const batchPlans=[];
      const retainProgram=async(result)=>{
        const bounded=await boundToolResult(result,{cwd,toolName:'agent_tools_execute',callId,maxChars:policy.output_bytes,retain:true});
        const saved=savedToolObservation(bounded);
        if(saved){
          const observation={...saved,ok:result.isError!==true,observedAt:Date.now(),receipt:result.details??{}};
          useLedger?.record('agent_tools_execute',callId,observation);
          if(scope?.task_id)useLedger?.record('agent_tools_execute','native-observation:'+scope.task_id+':'+createHash('sha256').update(callId).digest('hex'),observation);
        }
        return {isError:bounded.isError,content:bounded.content,details:bounded.details};
      };
      const failure=async error=>{
        return retainProgram({isError:true,content:[{type:'text',text:completedCalls.length?JSON.stringify({
        code:'composition_failed',message:String(error.message??error),completed_calls:completedCalls,
        completed_call_count:completedCalls.length,recovery:'Completed calls were not rolled back. Reuse their observation refs in this task; do not repeat them implicitly.'
      }):String(error.message??error)}]});
      };
      let child,timer;const abort=new AbortController(),queue=[],operations=new Set(),resourceFailures=new Map(),blocked=new Map();let active=0,calls=0,requests=0,skipped=0,reused=0,finished=false;
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
              if(message.kind==='preflight'||message.kind==='plan'){
                const reason=refreshReason(message.options);
                const basis=[];
                for(const ref of message.options?.basis_refs??[]){const record=await resolveRecord(ref);
                  if(!record||record.ok!==true)throw Error('/options/basis_refs: successful task-issued observations required');
                  basis.push({ref,status:record.value?.status??null});}
                const plan=message.calls,errors=[];
                if(!Array.isArray(plan)||!plan.length||plan.length>limit-requests)
                  throw Error(`Batch preflight: expected 1..${limit-requests} calls; no calls from this batch executed`);
                const prepared=plan.map((item,index)=>{
                  try{
                    if(!item||typeof item!=='object'||Object.keys(item).some(k=>!['tool','arguments'].includes(k))||
                        !item.arguments||typeof item.arguments!=='object'||Array.isArray(item.arguments))
                      throw Error('expected {tool,arguments:object}');
                    return {name:programIdentities.resolve(item.tool),args:structuredClone(item.arguments),options:reason?{refresh_reason:reason}:undefined};
                  }catch(e){errors.push({index,message:String(e.message??e)});return null;}
                });
                if(errors.length)throw Error('Batch preflight: no calls from this batch executed; '+JSON.stringify(errors));
                if(typeof validateCalls!=='function')throw Error('Batch argument validator unavailable; no calls from this batch executed');
                await validateCalls(prepared.map(item=>({name:item.name,arguments:item.args})),{signal:abort.signal});
                abort.signal.throwIfAborted();
                const keys=prepared.map(item=>item.name+':'+createHash('sha256').update(JSON.stringify(canonical(item.args))).digest('hex'));
                const existing=keys.flatMap((key,index)=>!reason&&successfulRequests.has(key)?[{index,ref:successfulRequests.get(key)}]:[]);
                const summary={requested_calls:prepared.length,distinct_requests:new Set(keys).size,
                  repeated_arguments:keys.length-new Set(keys).size,existing_observations:existing,
                  remaining_capacity:limit-requests,...(message.options?.purpose?{purpose:message.options.purpose,output:message.options.output,basis}:{}),
                  scope_assessment:'Counts and references only; business coverage and object selection are not certified'};
                // Another concurrent preflight can reserve while validation awaits.
                if(prepared.length>limit-requests)throw Error('Batch preflight: remaining capacity changed; no calls from this batch executed');
                // Reserve the entire batch before releasing a single call.
                if(message.kind==='plan')value=summary;
                else{requests+=prepared.length;batchPlans.push(summary);
                  const ref=randomUUID();batches.set(ref,prepared);value={ref,count:prepared.length};}
              }else{
              if(message.kind==='follow'){
                const action=observedAction(await sourceRecords(message.ref),message.ref,message.pointer);
                // No replacement arguments cross the worker boundary.
                message={...message,kind:'call',...action,options:{refresh_reason:'Follow the exact returned action at its scheduled time'}};
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
                const reason=refreshReason(message.options);
                const reusable=reuseEligible(schemas[message.name],message.args);
                if(active>=concurrency)await new Promise((resolve,reject)=>queue.push(()=>abort.signal.aborted?reject(abort.signal.reason):resolve()));
                abort.signal.throwIfAborted();active++;
                let release;
                try{
                  while(reusable&&inFlight.has(failureKey))await inFlight.get(failureKey);
                  abort.signal.throwIfAborted();
                  const previous=reusable&&!reason?successfulRequests.get(failureKey):undefined;
                  if(previous){
                    const record=records.get(previous);
                    reused++;completedCalls.push({ref:previous,tool:message.name,ok:true,reused:true});
                    value={...record.value,ref:previous,ok:true,value:record.value,reused:true,observed_at:new Date(record.observedAt).toISOString()};
                  }else if(rejectedRequests.has(failureKey)){
                    const previous=rejectedRequests.get(failureKey);
                    const refused=previous.gaps?.some(gap=>gap?.scope?.retry_same_request===false);
                    skipped++;value={ref:null,ok:false,status:'not_executed',data:null,
                      previous_call:previous.ref,gaps:previous.gaps,
                      recovery:refused?'This exact request was refused. scope.retry_same_request is false. Use scope.suggested_request when present, otherwise narrow by scope.fields in order. No upstream call was made.':'This exact request was already rejected as unexecuted and non-correctable. Inspect the previous observation; no new upstream call was made.',value:null};
                  }else if(blocked.has(failureKey)){
                    skipped++;value={ref:null,ok:false,status:'not_executed',data:null,gaps:[{reason:'repeated_resource_failure',tool:message.name,arguments_sha256:argumentsHash,scope:'unchanged_inputs'}],value:null};
                  }else{
                  if(reusable&&reason)successfulRequests.delete(failureKey);
                  if(reusable&&!inFlight.has(failureKey))inFlight.set(failureKey,new Promise(resolve=>{release=()=>{inFlight.delete(failureKey);resolve();};}));
                  calls++;
                  if(message.waitMs)await wait(message.waitMs,undefined,{signal:abort.signal});
                  const nestedId=`${callId}:${run}:${message.id}`,native=await restore(await invoke(message.name,message.args,{callId:nestedId,signal:abort.signal,...(reason?{refresh_reason:reason}:{})}));
                  const upstreamReuse=typeof native.details?.reused_from==='string';
                  if(upstreamReuse){calls--;reused++;}
                  let raw;try{raw=JSON.parse(native.content.find(c=>c.type==='text')?.text??'null');}catch{raw={text:native.content};}
                  const observed=raw?.structuredContent??raw;
                  const ref=`program-call:${run}:${message.id}`;
                  if(native.details?.kind==='external_gateway_observation')useLedger?.record(message.name,ref);
                  const ok=native.isError!==true&&!['error','failed','denied'].includes(observed?.status);
                  const timeout=!ok&&Array.isArray(observed?.gaps)&&observed.gaps.some(g=>/^(?:query_timeout|timeout|resource_exhausted|rate_limit)$/.test(g?.reason??''));
                  const count=timeout?(resourceFailures.get(failureKey)??0)+1:0;
                  resourceFailures.set(failureKey,count);
                  if(count>=policy.consecutive_resource_failures)blocked.set(failureKey,{tool:message.name,arguments_sha256:argumentsHash,scope:'unchanged_inputs'});
                  const observedAt=native.details?.observed_at?Date.parse(native.details.observed_at):Date.now();
                  records.set(ref,{ref,ok,value:observed,receipt:native.details??{},observedAt});
                  if(reusable&&ok&&observed?.status==='ok')successfulRequests.set(failureKey,ref);
                  const gaps=Array.isArray(observed?.gaps)?observed.gaps:[];
                  const refuseSame=!ok&&gaps.some(gap=>gap?.scope?.retry_same_request===false);
                  if(!ok&&(refuseSame||gaps.some(gap=>gap?.scope?.executed===false&&gap.scope.correctable===false)))
                    rejectedRequests.set(failureKey,{ref,gaps:structuredClone(gaps)});
                  completedCalls.push({ref,tool:message.name,ok,...(upstreamReuse?{reused:true,original_observation_ref:native.details.reused_from}:{}),...(reason?{refresh_reason:reason}:{})});
                  value={...(observed&&typeof observed==='object'?observed:{}),ref,ok,value:observed,
                    ...(refuseSame?{recovery:'Do not send this request again. Follow scope.suggested_request when present, otherwise equality-constrain scope.fields in order before any time range. limit does not narrow the scan before an aggregate.'}:{}),
                    ...(upstreamReuse?{reused:true,original_observation_ref:native.details.reused_from,observed_at:native.details.observed_at}:{})};
                  }
                }finally{release?.();active--;queue.shift()?.();}
              }else if(message.kind==='read'||message.kind==='inspect'){
                value=typeof message.ref==='string'?readObservation(await sourceRecords(message.ref),message.ref,message.pointer):
                  await readSavedObservation(message.ref,message.pointer,{cwd});
                if(message.kind==='inspect')value=structureIndex(value);
                const selectedValue=value;
                if(message.page!==undefined){
                  const page=message.page;
                  if(!page||typeof page!=='object'||Array.isArray(page)||Object.keys(page).some(k=>!['offset','limit'].includes(k))||
                      !Number.isSafeInteger(page.offset)||page.offset<0||!Number.isSafeInteger(page.limit)||page.limit<1||!Array.isArray(value))
                    throw Error('/page: expected {offset:nonnegative integer,limit:positive integer} for an array');
                  const end=Math.min(value.length,page.offset+page.limit);
                  value={items:value.slice(page.offset,end),offset:page.offset,total_items:value.length,next_offset:end<value.length?end:null};
                }
                if(Buffer.byteLength(JSON.stringify(value))>policy.output_bytes)
                  throw observationReadBudgetError(selectedValue,{ref:message.ref,pointer:message.pointer,
                    maximumBytes:policy.output_bytes,page:message.page});
              }else if(message.kind==='table')value=await prepareObservationTable({cwd,spec:message.spec,resolveRecord});
              else if(message.kind==='save')value=await saveSemanticContext({cwd,name:message.name,spec:message.spec,records,scope,resolveRecord});
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
        const failedCalls=completedCalls.filter(call=>!call.ok);
        const text=JSON.stringify({result:result??null,calls,skipped_calls:skipped,reused_call_count:reused,completed_calls:completedCalls,batch_plans:batchPlans,
          failed_call_count:failedCalls.length,failed_calls:failedCalls,limited_conditions:[...blocked.values()]});
        // Unlike gateway receipts, the program return has no host requirement
        // to inline original bytes. Keep the saved-file reference bounded even
        // when rpcEvent restores real upstream gateway observations.
        return retainProgram({isError:false,content:[{type:'text',text}],details:{kind:policy.schema,calls,reused_call_count:reused}});
      }catch(error){
        stop();await Promise.allSettled([...operations]);
        if(signal?.aborted)throw signal.reason??error;
        return await failure(error);
      }
      finally{clearTimeout(timer);stop();await Promise.allSettled([...operations]);}
    }};
}
