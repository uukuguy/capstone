import {fork} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {randomUUID,createHash} from 'node:crypto';
import {saveSemanticContext,loadSemanticContext} from './semantic-data-context.mjs';
import {boundToolResult} from './tool-result-context.mjs';
import {gatewayToolUseGuidance} from './gateway-tool-use.mjs';
export const compositionPolicy=Object.freeze(JSON.parse(readFileSync(new URL('./tool-composition-policy.json',import.meta.url),'utf8')));
const canonical=(v)=>Array.isArray(v)?v.map(canonical):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])])):v;
export function createToolCompositionTool({policy=compositionPolicy,cwd,catalog,invoke,scope,useLedger,deadlineAt=Infinity,allowedInputs=[],restore=async x=>x,onProgress=()=>{}}){
  // Session-local issued observations survive program calls, never task grants.
  // A different DR node must receive an explicit saved context package.
  const records=new Map();
  return {name:'agent_tools_execute',label:'组合工具与计算',description:'Run an async JavaScript program in the isolated task workspace. Select admitted gateway tools explicitly. Use Promise.all for independent calls and pass results directly to dependent calls. tools.call(name,args) returns {ref,ok,status,data,provenance,gaps,value}; tools.describe(name) returns its exact contract. python(code,data) runs Python with JSON stdin. saveContext(name,{bindings,datasets}) preserves observed source fields with call refs and JSON pointers, declared values, and unknown fields. loadContext(path) reuses a saved package. Return a compact summary; retain source data in packages. No automatic retries. Source packages are observations, not Authority evidence. '+gatewayToolUseGuidance,
    parameters:{type:'object',properties:{program:{type:'string',description:"Async program body. Example: const r=await tools.call(name,args); const saved=await saveContext('shared',{bindings:{unit:{call:r.ref,pointer:'/data/unit'},method:{value:'mean'},missing:{unknown:true,reason:'not provided'}},datasets:[{name:'load',call:r.ref,pointer:'/data/rows'}]}); return saved; Use actual returned fields in pointers. loadContext(saved.path) returns bindings with basis/value and datasets keyed by name with data/status/provenance/gaps. Plain binding values are declared metadata, never verified facts. Actual call refs remain usable by later programs in this instruction/session; different tasks need explicit saved packages. Large returns are saved automatically; return selected fields to reduce model context."},tools:{type:'array',items:{type:'string'}},purpose:{type:'string'},concurrency:{type:'integer',minimum:1,maximum:policy.concurrency},max_calls:{type:'integer',minimum:1,maximum:policy.max_calls},timeout_ms:{type:'integer',minimum:1,maximum:policy.max_program_ms}},required:['program','tools'],additionalProperties:false},
    async execute(callId,input,signal){
      signal?.throwIfAborted();
      const failure=error=>({isError:true,content:[{type:'text',text:String(error.message??error)}]});
      let child,timer;const abort=new AbortController(),queue=[],operations=new Set(),resourceFailures=new Map(),blocked=new Map();let active=0,calls=0,requests=0,skipped=0,finished=false;
      const stop=()=>{abort.abort(Error('Composition stopped'));for(const reject of queue.splice(0))reject();if(child?.pid){try{process.kill(-child.pid,'SIGKILL');}catch{child.kill('SIGKILL');}}};
      try{
        if(typeof input.program!=='string'||input.program.length>policy.code_chars)throw Error('Program code budget exceeded');
        if(!Array.isArray(input.tools)||input.tools.some(name=>!Object.hasOwn(catalog.tools,name)))throw Error('Unknown or ungranted selected tool');
        const limit=input.max_calls??policy.max_calls,concurrency=input.concurrency??policy.concurrency;
        if(!Number.isInteger(limit)||limit<1||limit>policy.max_calls||!Number.isInteger(concurrency)||concurrency<1||concurrency>policy.concurrency)throw Error('Invalid composition limits');
        const timeout=Math.min(input.timeout_ms??policy.max_program_ms,policy.max_program_ms,deadlineAt-Date.now());
        if(!Number.isFinite(timeout)||timeout<=0)throw Error('Composition timeout');
        const run=randomUUID(),schemas=Object.fromEntries(input.tools.map(name=>[name,catalog.tools[name]]));
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
              if(message.kind==='call'){
                if(!Object.hasOwn(schemas,message.name))throw Error('Tool not selected for this program');
                if(++requests>limit)throw Error('Composition call budget exceeded');
                const argumentsHash=createHash('sha256').update(JSON.stringify(canonical(message.args))).digest('hex');
                const failureKey=message.name+':'+argumentsHash;
                if(active>=concurrency)await new Promise((resolve,reject)=>queue.push(()=>abort.signal.aborted?reject(abort.signal.reason):resolve()));
                abort.signal.throwIfAborted();active++;
                try{
                  if(blocked.has(failureKey)){
                    skipped++;value={ref:null,ok:false,status:'not_executed',data:null,gaps:[{reason:'repeated_resource_failure',tool:message.name,arguments_sha256:argumentsHash,scope:'unchanged_inputs'}],value:null};
                  }else{
                  calls++;
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
                  records.set(ref,{ref,ok,value:observed,receipt:native.details??{}});
                  value={ref,ok,...(observed&&typeof observed==='object'?observed:{}),value:observed};
                  }
                }finally{active--;queue.shift()?.();}
              }else if(message.kind==='save')value=await saveSemanticContext({cwd,name:message.name,spec:message.spec,records,scope});
              else if(message.kind==='load')value=await loadSemanticContext({cwd,path:message.path,allowedInputs});
              else if(message.kind==='print'){value=undefined;onProgress(String(message.text).slice(0,policy.output_bytes));}
              else throw Error('Unknown composition request');
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
