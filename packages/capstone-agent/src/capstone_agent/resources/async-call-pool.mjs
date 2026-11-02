/** Neutral, instruction-owned work pool. No model choice, grants, persistence or retries. */
const terminal=new Set(['completed','failed','cancelled','blocked']);
const identifier=value=>typeof value==='string'&&value.trim().length>0&&value.length<=256&&!/[\x00-\x1f\x7f]/.test(value);
const positive=value=>Number.isSafeInteger(value)&&value>0;
const copy=value=>structuredClone(value);

export function createAsyncCallPool({concurrency,maxJobs,signal,run,onState=()=>{},
  now=Date.now,setTimer=setTimeout,clearTimer=clearTimeout}) {
  if(!positive(concurrency)||!positive(maxJobs)||concurrency>maxJobs||
    [run,onState,now,setTimer,clearTimer].some(fn=>typeof fn!=='function'))throw new TypeError('Invalid async call pool configuration');
  const records=new Map(),ready=[],waiters=new Set();
  let active=0,closed=false,pumping=false,closing,parentAttached=false;
  const publicRecord=record=>copy({id:record.job.id,status:record.status,
    depends_on:record.job.depends_on,...(record.job.attemptKey===undefined?{}:{attemptKey:record.job.attemptKey}),
    queuedAt:record.queuedAt,...(record.startedAt===undefined?{}:{startedAt:record.startedAt}),
    ...(record.finishedAt===undefined?{}:{finishedAt:record.finishedAt}),
    ...(record.result===undefined?{}:{result:record.result}),...(record.error?{error:record.error}:{}),
    ...(record.blockedBy?{blockedBy:record.blockedBy}:{}),...(record.cancelReason?{cancelReason:record.cancelReason}:{})});
  const snapshot=()=>({closed,active,pending:[...records.values()].filter(r=>!terminal.has(r.status)&&r.status!=='running'&&r.status!=='cancelling').length,
    jobs:[...records.values()].map(publicRecord)});
  const detach=()=>{if(closed&&active===0&&parentAttached){signal.removeEventListener('abort',parentAbort);parentAttached=false;}};
  const changed=record=>{
    // State notifications are presentation observations, never admission or persistence hooks.
    try{onState(publicRecord(record));}catch{/* A presentation observer cannot corrupt scheduling. */}
    for(const wake of [...waiters])wake();
  };
  const finish=(record,status,extra={})=>{
    if(terminal.has(record.status))return;
    if(record.timer!==undefined){clearTimer(record.timer);record.timer=undefined;}
    Object.assign(record,extra,{status,finishedAt:now()});ready.push(record);changed(record);
  };
  const requestCancel=(record,reason)=>{
    if(terminal.has(record.status)||record.status==='cancelling')return;
    record.cancelReason=reason;
    if(record.status==='running'){
      record.status='cancelling';
      if(record.timer!==undefined){clearTimer(record.timer);record.timer=undefined;}
      record.controller.abort();changed(record);
    }else finish(record,'cancelled');
  };
  function pump(){
    if(pumping)return;
    pumping=true;
    try{
      // Repeat to propagate blocked prerequisites declared after their descendants.
      let progress;
      do{
        progress=false;
        for(const record of records.values()){
          if(!['queued','waiting_dependencies'].includes(record.status))continue;
          if(closed||signal?.aborted){requestCancel(record,'parent_cancelled');progress=true;continue;}
          const dependencies=record.job.depends_on.map(id=>records.get(id));
          const failed=dependencies.filter(r=>terminal.has(r.status)&&r.status!=='completed');
          if(failed.length){finish(record,'blocked',{blockedBy:failed.map(r=>r.job.id)});progress=true;continue;}
          if(dependencies.some(r=>r.status!=='completed'))continue;
          if(record.status==='waiting_dependencies'){record.status='queued';changed(record);}
          if(active>=concurrency)continue;
          active++;record.status='running';record.controller=new AbortController();
          // The reservation remains held through cancellation until run's cleanup settles.
          record.task=Promise.resolve().then(async()=>{
            if(record.controller.signal.aborted)return;
            record.startedAt=now();
            if(record.job.timeoutMs!==undefined)record.timer=setTimer(()=>requestCancel(record,'timeout'),record.job.timeoutMs);
            changed(record);
            if(record.controller.signal.aborted)return;
            try{
              const result=await run(copy(record.job),{signal:record.controller.signal,
                dependencyResults:dependencies.map(r=>copy(r.result))});
              if(!result||typeof result!=='object'||Array.isArray(result)||!['completed','failed'].includes(result.status)){
                finish(record,record.status==='cancelling'?'cancelled':'failed',{error:{code:'invalid_run_result'}});
              }else{
                const retained=copy(result);
                finish(record,record.status==='cancelling'?'cancelled':retained.status,{result:retained});
              }
            }catch{
              finish(record,record.status==='cancelling'?'cancelled':'failed',{error:{code:'call_execution_failed'}});
            }
          }).finally(()=>{
            if(!terminal.has(record.status))finish(record,'cancelled');
            active--;pump();detach();for(const wake of [...waiters])wake();
          });
          progress=true;
        }
      }while(progress);
    }finally{pumping=false;}
  }
  function submit(jobs){
    if(closed||signal?.aborted)throw new Error('Async call pool is closed');
    if(!Array.isArray(jobs)||!jobs.length||records.size+jobs.length>maxJobs)throw new TypeError('Async call job budget exceeded');
    const batch=new Map(),attempts=new Set([...records.values()].filter(r=>!terminal.has(r.status)).map(r=>r.job.attemptKey).filter(x=>x!==undefined));
    for(const value of jobs){
      if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(key=>!['id','depends_on','input','timeoutMs','attemptKey'].includes(key))||
        !identifier(value.id)||records.has(value.id)||batch.has(value.id)||
        (value.attemptKey!==undefined&&(!identifier(value.attemptKey)||attempts.has(value.attemptKey)))||
        (value.timeoutMs!==undefined&&(!positive(value.timeoutMs)||value.timeoutMs>2147483647)))throw new TypeError('Invalid or duplicate async call identity');
      const depends=value.depends_on??[];
      if(!Array.isArray(depends)||depends.some(id=>!identifier(id))||new Set(depends).size!==depends.length)throw new TypeError('Invalid async call dependencies');
      const job=copy({...value,depends_on:depends});batch.set(job.id,job);
      if(job.attemptKey!==undefined)attempts.add(job.attemptKey);
    }
    const visited=new Set(),visiting=new Set();
    const visit=id=>{
      if(records.has(id)||visited.has(id))return;
      const job=batch.get(id);
      if(!job||visiting.has(id))throw new TypeError('Unknown or cyclic async call dependency');
      visiting.add(id);for(const dep of job.depends_on)visit(dep);visiting.delete(id);visited.add(id);
    };
    for(const id of batch.keys())visit(id);
    // All identities, inputs and the complete batch are checked before any call starts.
    for(const job of batch.values())records.set(job.id,{job,status:job.depends_on.length?'waiting_dependencies':'queued',queuedAt:now()});
    for(const job of batch.values())changed(records.get(job.id));
    pump();return snapshot();
  }
  const drainReady=()=>ready.splice(0).map(publicRecord);
  function cancel(ids){
    if(!Array.isArray(ids)||ids.some(id=>!records.has(id)))throw new TypeError('Unknown async call cancellation identity');
    for(const id of ids)requestCancel(records.get(id),'cancelled');pump();return snapshot();
  }
  function parentAbort(){
    closed=true;for(const record of records.values())requestCancel(record,'parent_cancelled');
    detach();for(const wake of [...waiters])wake();
  }
  function waitForCompletion({signal:waitSignal,waitMs=1000}={}){
    if(!positive(waitMs)||waitMs>60000)throw new TypeError('Invalid async call wait budget');
    const reason=()=>waitSignal?.aborted?'aborted':ready.length?'completion':active===0&&![...records.values()].some(r=>!terminal.has(r.status))?(closed?'closed':'idle'):undefined;
    const immediate=reason();if(immediate)return Promise.resolve({reason:immediate,snapshot:snapshot()});
    return new Promise(resolve=>{
      let timer,settled=false;
      const settle=why=>{
        if(settled)return;settled=true;waiters.delete(wake);waitSignal?.removeEventListener('abort',abort);
        if(timer!==undefined)clearTimer(timer);resolve({reason:why,snapshot:snapshot()});
      };
      const wake=()=>{const why=reason();if(why)settle(why);},abort=()=>settle('aborted');
      waiters.add(wake);waitSignal?.addEventListener('abort',abort,{once:true});
      timer=setTimer(()=>settle('timeout'),waitMs);wake();
    });
  }
  function close(){
    if(!closing){
      closed=true;for(const record of records.values())requestCancel(record,'closed');
      closing=Promise.all([...records.values()].map(r=>r.task).filter(Boolean)).then(()=>{detach();return snapshot();});
      detach();for(const wake of [...waiters])wake();
    }
    return closing;
  }
  if(signal){signal.addEventListener('abort',parentAbort,{once:true});parentAttached=true;}
  if(signal?.aborted)parentAbort();
  return Object.freeze({submit,drainReady,snapshot,waitForCompletion,cancel,close});
}
