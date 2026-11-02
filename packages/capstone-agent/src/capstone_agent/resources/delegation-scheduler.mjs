/** Neutral batch DAG scheduling. No model calls, evidence verdicts or retries. */
export function validateDelegationGraph(jobs) {
  if(!Array.isArray(jobs)||!jobs.length)throw new TypeError('Delegation needs tasks');
  const graph=new Map();
  for(const job of jobs){
    if(!job||typeof job.id!=='string'||!job.id.trim()||graph.has(job.id))throw new TypeError('Invalid or duplicate task ID');
    const dependencies=job.depends_on??[];
    if(!Array.isArray(dependencies)||dependencies.some(id=>typeof id!=='string')||new Set(dependencies).size!==dependencies.length)
      throw new TypeError('Invalid task dependencies');
    graph.set(job.id,[...dependencies]);
  }
  const visited=new Set(),active=new Set();
  const visit=id=>{
    if(!graph.has(id))throw new TypeError('Unknown task dependency');
    if(active.has(id))throw new TypeError('Cyclic task dependencies');
    if(visited.has(id))return;
    active.add(id);for(const dep of graph.get(id))visit(dep);active.delete(id);visited.add(id);
  };
  for(const id of graph.keys())visit(id);
  return graph;
}

export async function scheduleDelegation({jobs,concurrency,signal,run,onNotStarted=()=>{}}) {
  if(!Number.isSafeInteger(concurrency)||concurrency<1||typeof run!=='function')throw new TypeError('Invalid scheduler configuration');
  const graph=validateDelegationGraph(jobs),results=new Map(),pending=new Set(graph.keys()),running=new Map();
  let fatal;
  const settleUnstarted=async(job,status,blocked_by=[])=>{
    const result={status,blocked_by};pending.delete(job.id);
    try{await onNotStarted(job,result);}catch(error){fatal??=error;}
    results.set(job.id,result);
  };
  while(pending.size||running.size){
    for(const job of jobs){
      if(!pending.has(job.id))continue;
      if(signal?.aborted||fatal){await settleUnstarted(job,'cancelled');continue;}
      const deps=graph.get(job.id);
      const failed=deps.filter(id=>results.has(id)&&results.get(id).status!=='completed');
      if(failed.length){await settleUnstarted(job,'blocked',failed);continue;}
      if(running.size>=concurrency||!deps.every(id=>results.has(id)))continue;
      pending.delete(job.id);
      const task=Promise.resolve().then(()=>run(job,deps.map(id=>results.get(id))))
        .then(result=>{if(!result||!['completed','failed','cancelled','blocked'].includes(result.status))throw new TypeError('Invalid scheduled result');results.set(job.id,result);})
        .catch(error=>{fatal??=error;results.set(job.id,{status:'failed'});})
        .finally(()=>running.delete(job.id));
      running.set(job.id,task);
    }
    if(running.size)await Promise.race(running.values());
    else if(pending.size){
      // A previous pass may just have blocked a prerequisite that occurs later
      // in declaration order. The next pass propagates that terminal status.
      if(![...pending].some(id=>graph.get(id).some(dep=>results.has(dep))))throw new Error('Delegation scheduler made no progress');
    }
  }
  if(fatal)throw fatal;
  return jobs.map(job=>results.get(job.id));
}
