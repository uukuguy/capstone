/** Host-owned work-depth advice. This module never stops execution. */
export function taskTurnGuidance(policy,startedAt,now=Date.now()){
  if(policy===undefined)return undefined;
  const {target_seconds:target,integration_reserve_seconds:reserve}=policy;
  if(policy.mode!=='usable_draft'||!Number.isSafeInteger(target)||!Number.isSafeInteger(reserve)||
    target<=reserve||reserve<=0||!Number.isFinite(startedAt)||startedAt<=0||!Number.isFinite(now))
    throw new TypeError('Invalid task turn guidance');
  const elapsed=Math.max(0,Math.floor((now-startedAt)/1000));
  const phase=elapsed>=target?'deliver_available':elapsed>=target-reserve?'integration':'work';
  return {mode:policy.mode,advisory_only:true,started_at_ms:startedAt,target_seconds:target,
    integration_reserve_seconds:reserve,elapsed_seconds:elapsed,remaining_seconds:Math.max(0,target-elapsed),phase,
    instruction:(phase==='work'?'Produce a useful first answer within the assigned scope.':
      phase==='integration'?'Prefer integrating saved findings and requested deliverables now.':
      'Conclude with available findings, products and explicit gaps; do only essential remaining work.')+
      ' This is work-depth advice, not a cancellation deadline or a failure condition. Do not cancel a task or claim completion because time elapsed. Avoid optional analysis, extended repairs and repeated checks; the user can refine the result in the next turn.'};
}
