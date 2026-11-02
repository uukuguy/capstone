/**
 * Adapted from @tintinweb/pi-subagents 0.19.0 dist/agent-runner.js:
 * collectResponseText/getLastAssistantText/finalTurnError and runAgent execution.
 * Copyright (c) 2026 tintinweb. MIT; see LICENSE and UPSTREAM.md.
 *
 * The host supplies an already bound, guarded AgentSession. Resource discovery,
 * model selection, parent-history inheritance and completion validation are
 * supplied by the host. This is the upstream session execution path,
 * not the full extension, AgentManager or workflow scheduler.
 */
export function summarizeToolOperation(name, operation) {
  if (name !== 'bash') return operation.slice(0,180);
  const action=operation.replace(/^\s*cd\s+(?:'[^']*'|"[^"]*"|[^\s;&|]+)[ \t]*(?:&&|;|\r?\n)\s*/,'');
  const lines=action.split('\n'), first=lines[0]?.trim()??'';
  const comment=first.startsWith('#')&&!first.startsWith('#!')?first:
    /<<-?\s*['"]?[\w]+['"]?\s*$/.test(first)?lines[1]?.trim():undefined;
  const intent=comment?.startsWith('#')&&!comment.startsWith('#!')?comment.replace(/^#+\s*/,'').trim():'';
  return (intent||action).replace(/\s+/g,' ').trim().slice(0,180);
}

function extractText(content) {
  return content.filter(c => c.type === 'text').map(c => c.text ?? '').join('\n');
}

function collectResponseText(session) {
  let text = '';
  const unsubscribe = session.subscribe(event => {
    if (event.type === 'message_start' && event.message.role === 'assistant') text = '';
    if (event.type === 'message_update' && event.assistantMessageEvent.type === 'text_delta') {
      text += event.assistantMessageEvent.delta;
    }
  });
  return {getText: () => text, unsubscribe};
}

function getLastAssistantText(session, startIndex = 0) {
  for (let i = session.messages.length - 1; i >= startIndex; i--) {
    const msg = session.messages[i];
    if (msg.role !== 'assistant') continue;
    const text = extractText(msg.content).trim();
    if (text) return text;
  }
  return '';
}

function finalTurnError(session, startIndex = 0) {
  for (let i = session.messages.length - 1; i >= startIndex; i--) {
    const msg = session.messages[i];
    if (msg.role !== 'assistant') continue;
    if (msg.stopReason === 'error') return msg.errorMessage?.trim() || 'provider error with no output';
    if (msg.stopReason === 'length' && !extractText(msg.content).trim()) {
      return 'run hit the output token limit before producing any text';
    }
    return undefined;
  }
  return undefined;
}

// Report only usage supplied by the SDK. Missing pricing is unknown, not free.
function actualNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
}

export async function runManagedSession(session, prompt, options) {
  let turnCount = 0;
  let modelResponses = 0;
  let responseStarted;
  let softLimitReached = false;
  let aborted = false;
  let budgetExhausted=false,workSteered=false;
  let promptActive=false,promptStarted=false;
  const pastWorkDeadline=()=>options.workDeadline&&Date.now()>=options.workDeadline.finish_by_ms;
  const stopForWorkDeadline=()=>{
    budgetExhausted=true;
    // Host finalization is outside native execution. It can retain completed
    // work across this boundary, but it cannot start another correction turn.
    if(promptActive||!promptStarted){aborted=true;options.abort();}
  };
  const timers=[];
  if(options.workDeadline){
    const schedule=(at,fn)=>{const delay=Math.max(0,at-Date.now());timers.push(setTimeout(fn,delay));};
    schedule(options.workDeadline.wrapup_at_ms,()=>{
      if(options.signal?.aborted||aborted)return;
      workSteered=true;
      if(promptActive)session.steer('The shared task work window is closing. Save the useful outputs already computed and the existing exact contract manifest now. Mark unmet checks failed/not_run with actual limitations. Stop cosmetic changes and new scope, then return; do not invent missing evidence or recompute retained work.');
    });
    schedule(options.workDeadline.finish_by_ms,()=>{if(!options.signal?.aborted&&!aborted)stopForWorkDeadline();});
  }
  let currentMessageText = '';
  const usage = [];
  const unsubTurns = session.subscribe(event => {
    if (event.type === 'turn_start') {
      responseStarted = performance.now();
      options.onModelStart?.({response_number:modelResponses+1});
    }
    if (event.type === 'turn_end') {
      turnCount++;
      options.onTurnEnd?.(turnCount);
      // A settled final response needs no extra model turn to say it is final.
      if (options.maxTurns != null && !['stop','length','error','aborted'].includes(event.message?.stopReason)) {
        if (!softLimitReached && turnCount >= options.maxTurns) {
          softLimitReached = true;
          session.steer('You have reached your turn limit. Wrap up immediately — provide your final answer now.');
        } else if (softLimitReached && turnCount >= options.maxTurns + options.graceTurns && !aborted) {
          aborted = true;
          options.abort();
        }
      }
    }
    if (event.type === 'message_start') currentMessageText = '';
    if (event.type === 'message_update' && event.assistantMessageEvent.type === 'text_delta') {
      currentMessageText += event.assistantMessageEvent.delta;
      options.onTextDelta?.(event.assistantMessageEvent.delta, currentMessageText);
    }
    if (event.type === 'tool_execution_start' || event.type === 'tool_execution_end') {
      options.onToolActivity?.({
        type: event.type === 'tool_execution_start' ? 'start' : 'end',
        toolName: event.toolName,
        toolCallId: event.toolCallId,
        ...(event.args !== undefined ? {args: event.args} : {}),
        ...(event.result !== undefined ? {result: event.result} : {}),
        ...(typeof event.isError === 'boolean' ? {isError: event.isError} : {}),
      });
    }
    if (event.type === 'message_end' && event.message.role === 'assistant') {
      modelResponses++;
      if (responseStarted !== undefined) options.onModelResponse?.({
        response_number: modelResponses, response_ms: Math.max(0, Math.round(performance.now() - responseStarted)),
        tool_call_ids:(Array.isArray(event.message.content)?event.message.content:[])
          .filter(item=>item.type==='toolCall'&&typeof item.id==='string').map(item=>item.id),
        tool_requests:(Array.isArray(event.message.content)?event.message.content:[])
          .filter(item=>item.type==='toolCall'&&typeof item.id==='string').map(item=>{
            const operation=item.arguments?.command??item.arguments?.path??item.arguments?.file_path;
            return {id:item.id,name:String(item.name??'未知工具').slice(0,128),
              ...(typeof operation==='string'?{operation:summarizeToolOperation(item.name,operation)}:{})};
          }),
        response_text:extractText(Array.isArray(event.message.content)?event.message.content:[]).slice(0,600),
        ...(['stop','length','toolUse','error','aborted'].includes(event.message.stopReason)?{stop_reason:event.message.stopReason}:{})});
      responseStarted = undefined;
    }
    if (event.type === 'message_end' && event.message.role === 'assistant' && event.message.usage) {
      const u = event.message.usage;
      const actual = Object.freeze({input: actualNumber(u.input), output: actualNumber(u.output),
        cacheWrite: actualNumber(u.cacheWrite), cacheRead: actualNumber(u.cacheRead),
        totalTokens: actualNumber(u.totalTokens),
        cost: actualNumber(u.cost?.total)});
      usage.push(actual);
      options.onAssistantUsage?.(actual);
    }
    if (event.type === 'compaction_end' && !event.aborted && event.result) {
      options.onCompaction?.({reason: event.reason, tokensBefore: event.result.tokensBefore});
    }
  });
  const collector = collectResponseText(session);
  const startLen = session.messages.length;
  try {
    // Upstream 0.19 does not check a pre-aborted signal here. The managed seam
    // checks both allocation and prompt boundaries, including factory races.
    let next=prompt;
    while(options.signal?.aborted!==true&&!aborted){
      // The factory and host preflight can cross an absolute deadline before
      // timer0 has a chance to run. Check synchronously at every prompt boundary.
      if(pastWorkDeadline()){stopForWorkDeadline();break;}
      promptActive=true;promptStarted=true;
      try{await session.prompt(next);}finally{promptActive=false;}
      if(options.signal?.aborted===true||aborted||finalTurnError(session,startLen))break;
      // Trusted host completion checks run while this same session is alive.
      // Subscriptions, usage and the original lifetime turn budget stay intact.
      const followUp=await options.settledContinuation?.();
      if(pastWorkDeadline())stopForWorkDeadline();
      if(followUp==null||softLimitReached||workSteered||budgetExhausted)break;
      if(typeof followUp!=='string'||!followUp.trim())throw new TypeError('Child completion feedback requires a nonempty prompt');
      next=followUp;
    }
  } finally {
    for(const timer of timers)clearTimeout(timer);
    unsubTurns();
    collector.unsubscribe();
  }
  return {
    responseText: collector.getText().trim() || getLastAssistantText(session, startLen),
    aborted: aborted || options.signal?.aborted === true,
    steered: softLimitReached,
    ...(options.workDeadline?{budget_exhausted:budgetExhausted,work_steered:workSteered}:{}),
    failure: finalTurnError(session, startLen),
    turns: turnCount,
    modelResponses,
    usage: Object.freeze(usage),
    finish: (()=>{
      const message=session.messages.slice(startLen).filter(item=>item.role==='assistant').at(-1);
      const reason=message?.stopReason;
      return Object.freeze({stop_reason:['stop','length','toolUse','error','aborted'].includes(reason)?reason:null,
        visible_text_chars:Array.from(message?extractText(message.content):'').length,
        reasoning_tokens:actualNumber(message?.usage?.reasoning),
        model_output_capacity:actualNumber(session.model?.maxTokens),effective_output_limit:null});
    })(),
  };
}
