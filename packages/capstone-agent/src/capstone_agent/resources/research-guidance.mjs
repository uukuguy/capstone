/** Soft, bounded context reminders. They never invoke tools or veto completion. */
export function configureResearchGuidance(pi, guidance, {lightweight=false}={}) {
  if(typeof guidance!=='string'||!guidance.trim()||guidance.length>4000)return;
  if(lightweight){
    // Progress is execution advice, not a follow-up user asking for a status
    // answer. Keep the actual instruction last in the conversation context.
    pi.on('before_agent_start',event=>({systemPrompt:(event.systemPrompt??'')+
      '\nProgress reporting guidance (not a new user request):\n'+guidance+
      '\nA progress update does not replace the active instruction or its requested deliverables. Continue useful authorized work after reporting progress.'}));
    return;
  }
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
