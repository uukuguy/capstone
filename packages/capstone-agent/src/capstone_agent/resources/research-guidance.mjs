/** Soft, bounded context reminders. They never invoke tools or veto completion. */
export function configureResearchGuidance(pi, guidance, {lightweight=false,checkpointCalls=12}={}) {
  if(typeof guidance!=='string'||!guidance.trim()||guidance.length>4000)return;
  if(lightweight){
    if(!Number.isSafeInteger(checkpointCalls)||checkpointCalls<1||checkpointCalls>1024)
      throw new TypeError('Invalid investigation checkpoint interval');
    let completed=0,reviewed=0;
    const seen=new Set();
    const scope='Before exploratory work, state a finite scope, intended evidence and stopping or reconsideration conditions. '+
      'A selected skill supplies methods; it cannot expand the current instruction. '+
      'Empty samples establish only sampled absence, not absence from a table or source. '+
      'Separate source facts, hypotheses and inferred units. Verify the requested values in the final answer against source observations; successful execution is not goal attainment. '+
      'These are advisory reminders, not a budget guarantee for calls, time, tokens or cost.';
    pi.on('session_start',()=>{completed=0;reviewed=0;seen.clear();});
    pi.on('tool_execution_end',event=>{
      if(typeof event.toolCallId!=='string'||seen.has(event.toolCallId))return;
      seen.add(event.toolCallId);
      const receipt=event.result?.details;
      if(receipt?.kind==='capstone-tool-composition/1'){
        if(Number.isSafeInteger(receipt.completed_leaf_calls)&&receipt.completed_leaf_calls>=0)
          completed+=receipt.completed_leaf_calls;
      }else if(!receipt?.reused_from)completed++;
    });
    pi.on('context',event=>{
      if(completed-reviewed<checkpointCalls)return;
      const index=event.messages.findLastIndex(message=>message.role==='toolResult');
      if(index<0)return;
      const messages=[...event.messages],last=messages[index];
      messages[index]={...last,content:[...last.content,{type:'text',text:
        '[Host scope review; not source data] Scope review checkpoint: '+completed+' completed leaf calls. '+
        'Review progress against the current instruction and stated scope. Before expanding, explain what new evidence justifies it. '+
        'If useful progress is unavailable, return the scoped gap and retained findings. '+scope}]};
      reviewed=completed;
      return {messages};
    });
    // Progress is execution advice, not a follow-up user asking for a status
    // answer. Keep the actual instruction last in the conversation context.
    pi.on('before_agent_start',event=>({systemPrompt:(event.systemPrompt??'')+
      '\nProgress reporting guidance (not a new user request):\n'+guidance+
      '\nA progress update does not replace the active instruction or its requested deliverables. Continue useful authorized work after reporting progress. '+scope}));
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
