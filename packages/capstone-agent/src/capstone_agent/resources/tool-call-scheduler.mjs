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

export function applicationToolDispatcher(config,limit=8){
  const existing=applicationDispatchers.get(config);
  if(existing){
    if(existing.limit!==limit)throw Error('Application dispatch capacity changed');
    return existing;
  }
  const scheduler=createToolCallScheduler(limit);
  const dispatcher={limit,wrap(tool){
    // Only host executable factories declare this role. Remote catalog fields
    // do not enter executable objects. Containers must leave slots to leaves.
    if(tool.executionRole==='orchestrator'||tool[dispatchedBy]===dispatcher)return tool;
    const execute=tool.execute.bind(tool);
    return {...tool,[dispatchedBy]:dispatcher,async execute(callId,args,signal,...context){
      const release=await scheduler.acquire({signal});
      try{
        signal?.throwIfAborted();
        return await execute(callId,args,signal,...context);
      }finally{release();}
    }};
  }};
  applicationDispatchers.set(config,dispatcher);
  return dispatcher;
}
