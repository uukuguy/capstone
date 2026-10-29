/** A committed reader-facing delivery needs no second model-authored answer. */
export function finalizeCommittedDelivery(result){
  const delivery=result?.details?.ok===true&&result.isError!==true?result.details.result?.delivery:undefined;
  return delivery&&['success','limited'].includes(delivery.outcome)?{...result,terminate:true}:result;
}
export function configureCommittedDelivery(pi,controller){
  let committed;
  pi.on('tool_result',async(event,context)=>{
    if(event.toolName!=='agent_research_finish')return;
    const candidate=event.isError!==true&&event.details?.ok===true?event.details.result?.delivery:undefined;
    if(!candidate)return;
    const saved=(await controller.readState({compact:true})).delivery;
    if(!saved||!['success','limited'].includes(saved.outcome)||typeof saved.summary!=='string'||!saved.summary.trim()
      ||JSON.stringify(saved)!==JSON.stringify(candidate))return;
    context.signal?.throwIfAborted();
    committed=structuredClone(saved);
    // The finish tool's SDK terminate hint stops the completed batch. User
    // cancellation and actual model stop reasons are left unchanged.
  });
  return Object.freeze({delivery:()=>committed});
}
