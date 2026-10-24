/** Soft, bounded context reminders. They never invoke tools or veto completion. */
export function configureResearchGuidance(pi, guidance) {
  if(typeof guidance!=='string'||!guidance.trim()||guidance.length>4000)return;
  let pending='goal', firstWorkSeen=false;
  pi.on('tool_execution_end',event=>{
    if(event.toolName==='agent_task_progress') {
      const receipt=event.result?.details;
      if(event.isError!==true&&receipt?.ok===true) {
        const kind=receipt.result?.kind;
        // A goal can acknowledge the initial reminder, but cannot describe a
        // source result or failure that finished in the same tool batch.
        if(['observation','limitation','adjustment'].includes(kind)
            ||(kind==='goal'&&pending==='goal'))pending=null;
      }
      return;
    }
    if(event.isError===true)pending='result';
    if(!String(event.toolName??'').startsWith('agent_research_')&&!firstWorkSeen) {
      firstWorkSeen=true;
      pending='result';
    }
  });
  pi.on('context',async event=>{
    if(!pending)return;
    pending=null;
    return {messages:[...event.messages,{role:'user',content:guidance,timestamp:Date.now()}]};
  });
}
