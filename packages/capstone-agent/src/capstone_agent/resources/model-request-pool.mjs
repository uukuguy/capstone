import {createAsyncCallPool} from './async-call-pool.mjs';

const terminal=new Set(['completed','failed','cancelled','blocked']);
const safeId=value=>typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(value);
const opaqueId=value=>typeof value==='string'&&value.trim().length>0&&value.length<=128&&!/[\x00-\x1f\x7f\uD800-\uDFFF]/u.test(value);
const aborted=()=>Object.assign(new Error('Model request cancelled'),{name:'AbortError'});

// Match the SDK stream contract without creating an assistant message on failure.
function channel(){
  const queue=[],waiting=[];let ended=false,failure,resolveResult,rejectResult;
  const result=new Promise((resolve,reject)=>{resolveResult=resolve;rejectResult=reject;});
  // result() and iteration are independent consumers; either may be unused.
  result.catch(()=>{});
  return {
    push(value){if(ended)return;const waiter=waiting.shift();if(waiter)waiter.resolve({value,done:false});else queue.push(value);},
    complete(value){if(ended)return;ended=true;resolveResult(value);for(const waiter of waiting.splice(0))waiter.resolve({done:true});},
    fail(error){if(ended)return;ended=true;failure=error;rejectResult(error);for(const waiter of waiting.splice(0))waiter.reject(error);},
    result:()=>result,
    [Symbol.asyncIterator](){return {
      next(){if(queue.length)return Promise.resolve({value:queue.shift(),done:false});if(failure)return Promise.reject(failure);if(ended)return Promise.resolve({done:true});return new Promise((resolve,reject)=>waiting.push({resolve,reject}));},
      return:async()=>({done:true}),
    };},
  };
}

// SDK contexts include tool execute/argument callbacks as well as provider
// schemas. Copy mutable plain data while retaining these trusted callables.
// The caller's original AbortSignal is handled separately at dispatch.
function snapshotOptions(value){
  if(value===null||typeof value!=='object')return value;
  if(Array.isArray(value))return value.map(snapshotOptions);
  if(Object.getPrototypeOf(value)===Object.prototype||Object.getPrototypeOf(value)===null)
    return Object.fromEntries(Reflect.ownKeys(value).filter(key=>Object.prototype.propertyIsEnumerable.call(value,key)).map(key=>[key,snapshotOptions(value[key])]));
  if(value instanceof AbortSignal)return value;
  return structuredClone(value);
}

/**
 * All streamSimple requests share one finite instruction budget. Each chain
 * waits for the preceding request to settle, including provider drain. Distinct
 * SDK sessions must use distinct chains; this does not make concurrent prompt()
 * calls on one session safe. No retries, model selection or grants are added.
 *
 * streamSimple(model, context, options) returns an SDK-compatible async iterable
 * with result() immediately. Actual provider invocation starts only in a slot.
 * requestTimeoutMs is optional, starts at invocation, and only requests abort.
 * close() rejects queued consumers and drains active provider streams/results;
 * it cannot claim cleanup if a provider ignores cancellation and never settles.
 * drainChain(id) does not cancel: it waits until all submitted chain requests
 * have reached the internal scheduler terminal after cleanup. Call it after
 * closing the owning SDK session, so no later prompt extends that chain.
 * emit receives only public request identities, states and timestamps. The
 * application adds its selected event type/schema and owning task envelope.
 */
export function createModelRequestPool({runtime,concurrency,maxRequests,emit=()=>{},signal,requestTimeoutMs}){
  if(typeof runtime?.streamSimple!=='function'||typeof emit!=='function'||!Number.isSafeInteger(maxRequests)||maxRequests<1||
    (requestTimeoutMs!==undefined&&(!Number.isSafeInteger(requestTimeoutMs)||requestTimeoutMs<1||requestTimeoutMs>2147483647)))throw new TypeError('Invalid model request pool configuration');
  const entries=new Map(),events=new Map(),chains=new Map();let sequence=0,closing;
  function publish(entry,status,record={}){
    const previous=events.get(entry.id);
    if(previous&&terminal.has(previous.status))return;
    const event={request_id:entry.id,chain_id:entry.chainId,...entry.metadata,depends_on:entry.depends,
      status,queued_at_ms:record.queuedAt??previous?.queued_at_ms??Date.now(),
      ...(record.startedAt!==undefined?{started_at_ms:record.startedAt}:previous?.started_at_ms!==undefined?{started_at_ms:previous.started_at_ms}:{}),
      ...(terminal.has(status)?{finished_at_ms:record.finishedAt??Date.now()}:{}),
      ...(entry.cancelReason?{cancel_reason:entry.cancelReason}:{})};
    events.set(entry.id,event);
    if(JSON.stringify(previous)!==JSON.stringify(event))emit(structuredClone(event));
  }
  function detach(entry){if(entry.listenerAttached){entry.callerSignal.removeEventListener('abort',entry.callerAbort);entry.listenerAttached=false;}}
  function releaseChain(entry){
    const chain=chains.get(entry.chainId);if(!chain)return;
    chain.activeIds.delete(entry.id);
    if(!chain.activeIds.size){for(const resolve of chain.waiters)resolve();chain.waiters.clear();}
  }
  function cancel(entry,reason){
    if(entry.outcome||entry.cancelReason||terminal.has(events.get(entry.id)?.status))return;
    entry.cancelReason=reason;entry.controller.abort();entry.output.fail(aborted());detach(entry);
    publish(entry,entry.started?'cancelling':'cancelled');
    // No transport exists for a queued request. Remove it immediately rather
    // than retaining its chain barrier behind unrelated occupied slots.
    if(!entry.started)pool.cancel([entry.id]);
  }
  const pool=createAsyncCallPool({concurrency,maxJobs:maxRequests,signal,
    onState:record=>{
      const entry=entries.get(record.id);if(!entry)return;
      if(record.status==='running'){
        entry.started=true;
        if(!entry.cancelReason)publish(entry,'running',record);
      }else if(record.status==='cancelling')cancel(entry,record.cancelReason??'parent_cancelled');
      else if(terminal.has(record.status)){
        if(!entry.outcome){entry.output.fail(aborted());entry.cancelReason??=record.cancelReason??'parent_cancelled';}
        try{publish(entry,entry.cancelReason?'cancelled':entry.outcome??'cancelled',record);}
        finally{detach(entry);entries.delete(entry.id);releaseChain(entry);}
      }else if(!entry.cancelReason)publish(entry,record.status,record);
    },
    run:async(job,{signal:poolSignal})=>{
      const entry=entries.get(job.input);if(!entry)return {status:'completed'};
      if(entry.cancelReason)return {status:'completed'};
      const abort=()=>cancel(entry,'parent_cancelled');poolSignal.addEventListener('abort',abort,{once:true});
      if(poolSignal.aborted)abort();
      let timer;
      try{
        if(entry.cancelReason)return {status:'completed'};
        if(requestTimeoutMs!==undefined)timer=setTimeout(()=>cancel(entry,'timeout'),requestTimeoutMs);
        const actual=await runtime.streamSimple(entry.model,entry.context,{...entry.options,signal:entry.controller.signal});
        if(!actual||typeof actual[Symbol.asyncIterator]!=='function'||typeof actual.result!=='function')throw new TypeError('Invalid provider stream');
        const result=Promise.resolve().then(()=>actual.result());result.catch(()=>{});
        let streamFailure,resultFailure,returned;
        try{for await(const event of actual)entry.output.push(event);}catch(error){streamFailure=error;}
        // An iterator failure alone does not prove provider cleanup. Retain the
        // reservation until its result promise has also settled.
        try{returned=await result;}catch(error){resultFailure=error;}
        if(entry.cancelReason)entry.output.fail(aborted());
        else if(streamFailure||resultFailure){entry.outcome='failed';entry.output.fail(streamFailure??resultFailure);}
        else{entry.outcome=['error','aborted'].includes(returned?.stopReason)?'failed':'completed';entry.output.complete(returned);}
      }catch(error){entry.outcome='failed';entry.output.fail(entry.cancelReason?aborted():error);}
      finally{clearTimeout(timer);poolSignal.removeEventListener('abort',abort);detach(entry);
        // Large private snapshots are not retained by the pool's state history.
        entry.model=undefined;entry.context=undefined;entry.options=undefined;
      }
      // Scheduling depends on returned/failed settlement, not provider success.
      // Caller cancellation uses the provider signal, rather than poisoning a
      // chain's dependency with the scheduler's failed-prerequisite semantics.
      return {status:'completed'};
    }});
  function forChain(chainId,metadata={}){
    if(!safeId(chainId)||!(chainId==='main'||chainId.startsWith('analysis:')))throw new TypeError('Invalid model request chain');
    const kind=chainId==='main'?'main':'analysis';
    if(metadata.kind!==undefined&&metadata.kind!==kind||metadata.getModelTurnNumber!==undefined&&typeof metadata.getModelTurnNumber!=='function')throw new TypeError('Invalid host model turn binding');
    if(metadata.title!==undefined&&(typeof metadata.title!=='string'||!metadata.title.trim()||metadata.title.length>120||/[\x00-\x1f\x7f]/.test(metadata.title)))throw new TypeError('Invalid model request title');
    const selected=kind==='main'?{kind}:{kind,child_id:metadata.child_id,parent_tool_call_id:metadata.parent_tool_call_id,...(metadata.title===undefined?{}:{title:metadata.title})};
    if(selected.kind==='analysis'&&(!opaqueId(selected.child_id)||!safeId(selected.parent_tool_call_id)))throw new TypeError('Invalid analysis request identity');
    const existing=chains.get(chainId);
    if(existing&&JSON.stringify(existing.metadata)!==JSON.stringify(selected))throw new TypeError('Model request chain identity changed');
    if(existing){if(metadata.getModelTurnNumber)existing.getModelTurnNumber=metadata.getModelTurnNumber;return existing.proxy;}
    if(chains.size>=maxRequests+1)throw new TypeError('Model request chain budget exceeded');
    const chain={metadata:selected,last:undefined,proxy:undefined,requests:0,getModelTurnNumber:metadata.getModelTurnNumber,activeIds:new Set(),waiters:new Set()};
    const enqueue=(model,context,options={})=>{
        const turn=chain.getModelTurnNumber?.()??chain.requests+1;
        if(!Number.isSafeInteger(turn)||turn<1)throw new TypeError('Invalid host model turn number');
        const capturedModel=snapshotOptions(model),capturedContext=snapshotOptions(context),capturedOptions=snapshotOptions(options);
        const output=channel(),id=`request-${++sequence}`;
        const entry={id,chainId,metadata:{...selected,model_turn_number:turn,...(kind==='main'?{title:`LLM ${turn}`}:{})},depends:chain.last?[chain.last]:[],output,
          model:capturedModel,context:capturedContext,options:capturedOptions,controller:new AbortController(),
          callerSignal:options.signal,listenerAttached:false,started:false,cancelReason:undefined,outcome:undefined};
        entry.callerAbort=()=>cancel(entry,'cancelled');entries.set(id,entry);chain.activeIds.add(id);
        // Public provenance always names the previous request. Internally only
        // an uncertain predecessor must hold the next explicit request back.
        const schedulingDependencies=entry.depends.filter(previous=>!terminal.has(events.get(previous)?.status));
        try{pool.submit([{id,input:id,depends_on:schedulingDependencies}]);}
        catch(error){sequence--;entries.delete(id);releaseChain(entry);output.fail(error);throw error;}
        chain.last=id;chain.requests++;
        if(options.signal&&!terminal.has(events.get(id)?.status)){
          options.signal.addEventListener('abort',entry.callerAbort,{once:true});entry.listenerAttached=true;
          if(options.signal.aborted)entry.callerAbort();
        }
        return output;
    };
    let override;
    chain.proxy=new Proxy(runtime,{
      get(target,key){
        if(key==='streamSimple')return override??enqueue;
        const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
      },
      set(target,key,value){
        if(key==='streamSimple'){
          if(typeof value!=='function')throw new TypeError('Invalid chain stream override');
          // Debug wrappers call the previously read enqueue function. Never
          // replace the provider method that the worker invokes inside a slot.
          override=value===enqueue?undefined:value;return true;
        }
        return Reflect.set(target,key,value,target);
      },
    });
    chains.set(chainId,chain);return chain.proxy;
  }
  function close(){
    if(!closing){for(const entry of entries.values())cancel(entry,'closed');closing=pool.close().then(()=>{for(const entry of entries.values())detach(entry);entries.clear();return snapshot();});}
    return closing;
  }
  function snapshot(){const state=pool.snapshot();return {closed:state.closed,active:state.active,pending:state.pending,jobs:state.jobs.map(job=>structuredClone(events.get(job.id)))};}
  function drainChain(chainId){
    if(!safeId(chainId)||!(chainId==='main'||chainId.startsWith('analysis:')))throw new TypeError('Invalid model request chain');
    const chain=chains.get(chainId);
    if(!chain?.activeIds.size)return Promise.resolve();
    return new Promise(resolve=>chain.waiters.add(resolve));
  }
  return Object.freeze({runtime:forChain('main'),forChain,drainChain,close,snapshot});
}
