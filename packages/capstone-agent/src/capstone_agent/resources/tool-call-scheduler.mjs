import {randomUUID} from 'node:crypto';

// Session-local FIFO capacity. Unknown or mutating operations hold an exclusive
// lease. This is not a gateway-wide or cross-process capacity controller.
export function createToolCallScheduler(limit){
  if(!Number.isSafeInteger(limit)||limit<1)throw Error('Invalid scheduler limit');
  let active=0,exclusiveActive=false;const queue=[];
  const drain=()=>{
    while(queue.length){
      const entry=queue[0];
      if(exclusiveActive||active>=limit||(entry.exclusive&&active))return;
      queue.shift();entry.signal?.removeEventListener('abort',entry.cancel);
      active++;exclusiveActive=entry.exclusive;
      let released=false;
      entry.resolve(()=>{if(released)return;released=true;active--;if(entry.exclusive)exclusiveActive=false;drain();});
      if(entry.exclusive)return;
    }
  };
  return {acquire({signal,exclusive=false}={}){
    signal?.throwIfAborted();
    return new Promise((resolve,reject)=>{
      const entry={signal,exclusive,resolve,reject};
      entry.cancel=()=>{const index=queue.indexOf(entry);if(index<0)return;queue.splice(index,1);reject(signal.reason??Error('Call cancelled'));drain();};
      queue.push(entry);signal?.addEventListener('abort',entry.cancel,{once:true});drain();
    });
  }};
}

const applicationDispatchers=new WeakMap();
const dispatchedBy=Symbol('hostApplicationDispatcher');

// SDK launch boundaries determine membership and elapsed time. Per-tool
// execution intervals do not determine whether a batch is parallel.
export function createToolBatchObserver({taskId,emit,capacity=8,clock=()=>performance.now()}){
  let pending,started;
  return event=>{
    if(event.type==='message_end'&&event.message?.role==='assistant'){
      const ids=(event.message.content??[]).filter(part=>part.type==='toolCall').map(part=>part.id);
      pending=ids.length?{schema:'capstone-tool-batch/1',task_id:taskId,batch_id:randomUUID(),mode:'parallel',capacity,call_ids:ids}:undefined;
      started=undefined;
    }
    if(event.type==='tool_execution_start'&&pending?.call_ids.includes(event.toolCallId)&&started===undefined)started=clock();
    if(event.type==='turn_end'&&pending&&started!==undefined){
      emit({type:'tool_batch',tool_batch:{...pending,elapsed_ms:Math.max(0,clock()-started)}});
      pending=undefined;started=undefined;
    }
  };
}

export function applicationToolDispatcher(config,limit=8,{observe}={}){
  const existing=applicationDispatchers.get(config);
  if(existing){
    if(existing.limit!==limit)throw Error('Application dispatch capacity changed');
    if(observe)existing.observe=observe;
    return existing;
  }
  const scheduler=createToolCallScheduler(limit);
  const origin=performance.now(),wallOrigin=Date.now(),owner='native-dispatch:'+randomUUID();
  const dispatcher={limit,observe,wrap(tool){
    // Only host executable factories declare this role. Remote catalog fields
    // do not enter executable objects. Containers must leave slots to leaves.
    if(tool.executionRole==='orchestrator'||tool[dispatchedBy]===dispatcher)return tool;
    const execute=tool.execute.bind(tool);
    return {...tool,[dispatchedBy]:dispatcher,async execute(callId,args,signal,...context){
      signal?.throwIfAborted();
      const events=[],taskId=config.taskId??config.researchTaskId;
      const mark=phase=>{const elapsed=Number((performance.now()-origin).toFixed(3));events.push({
        phase,elapsed_ms:elapsed,at:new Date(wallOrigin+elapsed).toISOString(),provenance:'native_dispatch'});};
      mark('submitted');mark('queued');
      let release;
      try{
        release=await scheduler.acquire({signal});mark('acquired');
        signal?.throwIfAborted();
        mark('invocation_started');
        try{return await execute(callId,args,signal,...context);}
        finally{mark('invocation_settled');}
      }finally{
        release?.();mark('released');
        if(typeof taskId==='string'&&taskId&&typeof callId==='string'&&callId){
          dispatcher.observe?.({schema:'capstone-tool-dispatch/1',owner_id:owner,scope_id:taskId,
            task_id:taskId,call_id:callId,policy_version:'native-dispatch/1',capacity:limit,events},tool.name);
        }
      }
    }};
  }};
  applicationDispatchers.set(config,dispatcher);
  return dispatcher;
}
