import {createHash} from 'node:crypto';
import {createAsyncCallPool} from './async-call-pool.mjs';
import {boundToolResult} from './tool-result-context.mjs';

export const llmCallToolNames=['agent_llm_submit','agent_llm_collect','agent_llm_cancel'];
const finalStates=new Set(['completed','failed','cancelled','blocked']);
const reply=value=>({content:[{type:'text',text:JSON.stringify(value)}]});
const exact=(value,keys)=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).every(key=>keys.includes(key));

export function buildLlmCallPrompt(input,dependencyResults,policy){
  const prompt=JSON.stringify({instruction:input.instruction,observations:input.input,
    prerequisites:dependencyResults.map(result=>({answer:result.answer,answer_truncated:result.answer_truncated??false}))});
  if(prompt.length>policy.max_input_chars)throw new RangeError('LLM assembled input budget exceeded');
  return prompt;
}

/** Explicit text-only reasoning. No model choice, business grants or retries. */
export function createLlmCallTools({policy,run,emit=()=>{},signal,cwd=process.cwd()}){
  if(!policy||policy.schema!=='capstone-llm-call-pool/1'||typeof run!=='function')throw new TypeError('Invalid LLM pool configuration');
  const inputs=new Map(),unread=new Map(),needsIntegration=new Set();
  let sink,delivery=Promise.resolve(),revision=0,closing=false;
  const state=()=>{const snapshot=pool.snapshot();return {...snapshot,jobs:snapshot.jobs.map(({result,...record})=>record)}};
  const capture=()=>{for(const record of pool.drainReady()){unread.set(record.id,record);needsIntegration.add(record.id)}};
  const flush=()=>{
    delivery=delivery.catch(()=>{}).then(async()=>{
      capture();if(!sink||!unread.size||closing)return;
      const results=[...unread.values()];
      await sink({schema:policy.schema,results,pool:state(),basis:'Returned model observations; not Authority results or verification.'});
      for(const record of results)unread.delete(record.id);
    });return delivery;
  };
  const pool=createAsyncCallPool({concurrency:policy.concurrency,maxJobs:policy.max_jobs,signal,
    onState:record=>{
      revision++;emit({...record,input:inputs.get(record.id)});
      if(finalStates.has(record.status)&&sink&&!closing)queueMicrotask(()=>void flush().catch(()=>{}));
    },
    run:async(job,context)=>{
      const result=await run({...job,input:inputs.get(job.id)},context);
      if(result&&typeof result.answer==='string'&&result.answer.length>policy.max_output_chars){
        const saved=await boundToolResult({content:[{type:'text',text:JSON.stringify(result)}]},
          {cwd,toolName:'agent_llm_submit',callId:job.id,maxChars:Math.max(1500,Math.min(6000,policy.max_output_chars))});
        const reference=JSON.parse(saved.content[0].text).full_result;
        return {...result,answer:result.answer.slice(0,policy.max_output_chars),answer_truncated:true,full_result:reference};
      }
      return result;
    }});
  const status=()=>({schema:policy.schema,results:[],pool:state()});
  const tools=[{
    name:llmCallToolNames[0],label:'提交并行分析',
    description:'Submit independent text analysis calls to the instruction-owned LLM pool and return immediately. Supply actual observations explicitly. Calls have no tools or external lookup. Dependencies receive actual successful returned answers. Continue independent work, then collect. This does not enable Deep Research. Never resubmit an uncertain running call; inspect or cancel it first.',
    parameters:{type:'object',additionalProperties:false,required:['calls'],properties:{calls:{type:'array',minItems:1,maxItems:policy.max_jobs,items:{type:'object',additionalProperties:false,required:['id','instruction','input'],properties:{
      id:{type:'string',minLength:1,maxLength:128},instruction:{type:'string',minLength:1,maxLength:policy.max_input_chars},
      input:{type:'string',maxLength:policy.max_input_chars,description:'Explicit observed data or text, including source/version/units/limitations needed for this analysis. Not a file path to read.'},
      depends_on:{type:'array',uniqueItems:true,items:{type:'string',minLength:1,maxLength:128}}}}}}},
    async execute(_id,args,callSignal){
      callSignal?.throwIfAborted();
      if(!exact(args,['calls'])||!Array.isArray(args.calls)||!args.calls.length)throw new TypeError('Invalid LLM calls');
      const jobs=args.calls.map(call=>{
        if(!exact(call,['id','instruction','input','depends_on'])||typeof call.id!=='string'||call.id.length>128||
          typeof call.instruction!=='string'||!call.instruction.trim()||typeof call.input!=='string'||
          call.instruction.length+call.input.length>policy.max_input_chars)throw new TypeError('Invalid LLM input budget');
        const input={instruction:call.instruction,input:call.input};
        const attemptKey=createHash('sha256').update(JSON.stringify([input,call.depends_on??[]])).digest('hex');
        return {id:call.id,input:{...input,parentToolCallId:_id},depends_on:call.depends_on??[],timeoutMs:policy.call_timeout_ms,attemptKey};
      });
      // Pool validates atomically before run's microtask can read these inputs.
      if(jobs.some(job=>inputs.has(job.id)))throw new TypeError('Invalid duplicate LLM call ID');
      for(const job of jobs)inputs.set(job.id,job.input);
      try{pool.submit(jobs)}catch(error){for(const job of jobs)inputs.delete(job.id);throw error}
      return reply(status());
    }
  },{
    name:llmCallToolNames[1],label:'接收并行分析',
    description:'Collect actual returned analysis results and current queued/running/cancelling states. Set wait_ms only when no independent work remains. A collection wait timeout is not a model failure and must not cause a duplicate retry. Completed results may already have arrived in the conversation asynchronously.',
    parameters:{type:'object',additionalProperties:false,properties:{wait_ms:{type:'integer',minimum:0,maximum:policy.max_wait_ms}}},
    async execute(_id,args,callSignal){
      if(!exact(args,['wait_ms'])||!Number.isSafeInteger(args.wait_ms??0)||(args.wait_ms??0)<0||(args.wait_ms??0)>policy.max_wait_ms)throw new TypeError('Invalid LLM collection wait');
      callSignal?.throwIfAborted();await delivery.catch(()=>{});capture();let reason='snapshot';
      if(!unread.size&&args.wait_ms){reason=(await pool.waitForCompletion({signal:callSignal,waitMs:args.wait_ms})).reason;capture()}
      const results=[...unread.values()];unread.clear();
      return reply({...status(),results,wait_reason:reason});
    }
  },{
    name:llmCallToolNames[2],label:'取消并行分析',
    description:'Request cancellation of selected calls. Running calls keep their capacity reservation until cleanup actually completes; cancelling is not settled. No retries are started.',
    parameters:{type:'object',additionalProperties:false,required:['ids'],properties:{ids:{type:'array',uniqueItems:true,items:{type:'string',minLength:1}}}},
    async execute(_id,args,callSignal){callSignal?.throwIfAborted();if(!exact(args,['ids']))throw new TypeError('Invalid LLM cancellation');pool.cancel(args.ids);return reply(status())}
  }];
  return {tools,setCompletionSink:value=>{sink=value;void flush().catch(()=>{})},flush,
    acknowledge:ids=>{for(const id of ids)needsIntegration.delete(id)},
    async continuation(){
      await flush().catch(()=>{});capture();const snapshot=state();
      if(!unread.size&&!needsIntegration.size&&!snapshot.jobs.some(job=>!finalStates.has(job.status)))return;
      return {actionId:'lightweight-llm-pool',checkpoint:{revision,needs_integration:[...needsIntegration]},
        prompt:'LLM pool work remains unresolved or uncollected. Continue independent work or use agent_llm_collect to receive actual results; explicitly cancel unnecessary jobs. Do not finalize with unseen answers. Current state: '+JSON.stringify(snapshot)};
    },
    close(){closing=true;return pool.close()},snapshot:state};
}
