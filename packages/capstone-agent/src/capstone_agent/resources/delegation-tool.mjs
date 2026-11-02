import {completeDeliveryReview} from './delivery-review.mjs';
import {scheduleDelegation,validateDelegationGraph} from './delegation-scheduler.mjs';
const USAGE_FIELDS = ['input', 'output', 'cacheRead', 'cacheWrite', 'totalTokens', 'cost'];

function checkedFinish(value){
  const number=key=>typeof value[key]==='number'&&Number.isFinite(value[key])&&value[key]>=0?value[key]:null;
  return {stop_reason:['stop','length','toolUse','error','aborted'].includes(value.stop_reason)?value.stop_reason:null,
    visible_text_chars:number('visible_text_chars'),reasoning_tokens:number('reasoning_tokens'),
    model_output_capacity:number('model_output_capacity'),effective_output_limit:number('effective_output_limit')};
}

function actualUsage(value) {
  return Object.freeze(Object.fromEntries(USAGE_FIELDS.map(key => [key,
    typeof value?.[key] === 'number' && Number.isFinite(value[key]) && value[key] >= 0 ? value[key] : null])));
}

function aggregateUsage(children) {
  const observations = children.flatMap(child => child.usage);
  const missingChildUsage = children.some(child => !child.usage.length && child.error?.code !== 'child_not_started');
  return Object.fromEntries(USAGE_FIELDS.map(key => {
    if (missingChildUsage || !observations.length || observations.some(item => item[key] === null)) return [key, null];
    const sum = observations.reduce((total, item) => total + item[key], 0);
    return [key, Number.isFinite(sum) ? sum : null];
  }));
}

function exactKeys(value, keys) {
  return value && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}
const nonempty=value=>typeof value==='string'&&value.trim().length>0;
function freeze(value){
  if(value&&typeof value==='object'){for(const child of Object.values(value))freeze(child);Object.freeze(value);}
  return value;
}
function checkedBinding(value){
  if(!exactKeys(value,['owner','attempt_id','parent_action_id','parent_step_id','checkpoint',...(value?.review_mode!==undefined?['review_mode']:[])])||
    (value.review_mode!==undefined&&value.review_mode!=='delivery')||
    !exactKeys(value.owner,['thread_id','work_id','research_id','goal_revision'])||
    !['thread_id','work_id','research_id'].every(key=>nonempty(value.owner[key]))||
    !Number.isSafeInteger(value.owner.goal_revision)||value.owner.goal_revision<1||
    !['attempt_id','parent_action_id','parent_step_id'].every(key=>nonempty(value[key]))||
    !exactKeys(value.checkpoint,['ref','revision'])||!nonempty(value.checkpoint.ref)||
    !Number.isSafeInteger(value.checkpoint.revision)||value.checkpoint.revision<1)
    throw new TypeError('Invalid host delegation binding');
  // Explicit field selection prevents a task or future private host field from
  // becoming part of the public subordinate event by accidental object spread.
  return freeze({owner:{thread_id:value.owner.thread_id,work_id:value.owner.work_id,research_id:value.owner.research_id,
    goal_revision:value.owner.goal_revision},attempt_id:value.attempt_id,parent_action_id:value.parent_action_id,
    parent_step_id:value.parent_step_id,checkpoint:{ref:value.checkpoint.ref,revision:value.checkpoint.revision},...(value.review_mode==='delivery'?{review_mode:'delivery'}:{})});
}

function validateTasks(params, maxTasks) {
  if (!params||typeof params!=='object'||Array.isArray(params)||!Object.hasOwn(params,'tasks')||Object.keys(params).some(key=>!['tasks','review_products','review_source_refs'].includes(key))|| !Array.isArray(params.tasks)
      || params.tasks.length < 1 || params.tasks.length > maxTasks) {
    throw new TypeError('Invalid delegation tasks or task count');
  }
  const ids = new Set();
  return Object.freeze(params.tasks.map(task => {
    const fields=['id','title','instruction','questions','expected_outputs','depends_on'];
    if (!task||typeof task!=='object'||Array.isArray(task)||Object.keys(task).some(key=>!fields.includes(key))
        || !['id', 'title', 'instruction'].every(key => typeof task[key] === 'string' && task[key].trim())
        || ['questions','expected_outputs','depends_on'].some(key=>Object.hasOwn(task,key)&&
          (!Array.isArray(task[key])||!task[key].every(nonempty)))
        || ids.has(task.id)) throw new TypeError('Invalid delegation task identity or fields');
    ids.add(task.id);
    return freeze({id:task.id,title:task.title,instruction:task.instruction,
      ...Object.fromEntries(['questions','expected_outputs','depends_on'].filter(key=>Object.hasOwn(task,key)).map(key=>[key,[...task[key]]]))});
  }));
}

/**
 * Application-granted native delegation only. The host supplies all limits and
 * runChild(job,{signal,onToolActivity,onAssistantUsage,onTextDelta,onTurnEnd}).
 * The runner owns the child's admitted tools/model/private context and cleanup.
 * This pool adds no durable state, runtime, retry, tool grants or model choice.
 * Optional admitTasks(jobs,{toolCallId,signal}) returns the host-owned committed
 * parent binding once per batch. Its rejection starts no child. Generic callers
 * may omit admission and question metadata; the host owns research requirements.
 *
 * A returned failure string must already be safe for model/public consumption.
 * Thrown errors never expose raw messages. emit is a synchronous host callback;
 * its events are subordinate observations, never parent task-step completion.
 */
export function delegationScopePrompt(siblings = []) {
  return '\nWork only on the assigned questions and expected outputs. Other assignments in this batch: '+JSON.stringify(siblings)+
    '\nUse the supplied results and source references needed for your assignment. Do not repeat a sibling assignment or expand into a full end-to-end investigation. '+
    'If you find a question owned by another branch, return the concrete concern and evidence location for parent integration instead of solving it yourself. '+
    'Necessary checks within your own assignment are allowed. Prefer a direct check that answers the question using the stated source conventions. '+
    'Batch related reads and calculations when they do not depend on intermediate results. Once the question has sufficient evidence, return the finding, evidence location and unchecked scope. '+
    'Do not keep testing hypothetical alternative conventions, create a second parser, or generate additional reports merely to increase confidence. '+
    'Further work is warranted by a concrete discrepancy, missing evidence, material risk or an explicit request for independent replication. '+
    'Return findings directly unless saved files are needed by the assignment or a dependent task. An incomplete or failed check must remain explicit; never present it as verified. '+
    'If a local check fails and a focused correction does not resolve it, record the failure and continue with available findings; do not keep repairing the same check. '+
    'Do not infer that another branch has succeeded from its assignment; only the parent can integrate actual returned results.';
}

export function createDelegationTool({runChild, concurrency, maxTasks, emit,admitTasks,prepareReview}) {
  if (typeof runChild !== 'function') throw new TypeError('runChild is required');
  for (const [name, value] of [['concurrency', concurrency], ['maxTasks', maxTasks]]) {
    if (!Number.isSafeInteger(value) || value < 1) throw new TypeError(name + ' must be a positive safe integer');
  }
  if (emit !== undefined && typeof emit !== 'function') throw new TypeError('emit must be a function');
  if (admitTasks !== undefined && typeof admitTasks !== 'function') throw new TypeError('admitTasks must be a function');
  if (prepareReview !== undefined && typeof prepareReview !== 'function') throw new TypeError('prepareReview must be a function');
  return {
    name: 'agent_delegate',
    label: 'Delegate independent tasks',
    description: 'Run explicit independent tasks in host-managed native child sessions. Each child returns its actual answer, status and observed usage. Children cannot select their own model, tools or permissions. These are general observations, not Authority evidence; the parent must assess and integrate them.',
    parameters: {
      type: 'object', additionalProperties: false, required: ['tasks'],
      properties: {
        ...(prepareReview?{review_products:{type:'array',minItems:1,uniqueItems:true,items:{type:'string',minLength:1},description:'Saved workspace-relative final products and relevant supporting paths to independently review, before or after record. The host supplies actual current text/source versions to a fresh no-tool child. Findings require source verification, not automatic edits or factual/visual certification.'}}:{}),
        ...(prepareReview?{review_source_refs:{type:'array',uniqueItems:true,items:{type:'string',minLength:1},description:'Optional exact host-issued source references for intentional prior-version comparison. Original inputs and explicit selected context are included by default; automatic previous products require selection. No arbitrary paths or new read grants.'}}:{}),
        tasks: {type: 'array', minItems: 1, maxItems: maxTasks, items: {
        type: 'object', additionalProperties: false, required: ['id', 'title', 'instruction'],
        properties: {id: {type: 'string', minLength: 1}, title: {type: 'string', minLength: 1},
          instruction: {type: 'string', minLength: 1},
          depends_on:{type:'array',uniqueItems:true,items:{type:'string',minLength:1},description:'IDs of tasks in this batch whose successful returned observations are needed first. Empty or omitted means independent; independent ready tasks run together up to configured capacity.'},
          questions:{type:'array',items:{type:'string',minLength:1},description:'Independent questions for this child. Managed research requires a nonempty subset of the accepted parent action questions; generic applications may omit this field.'},
          expected_outputs:{type:'array',items:{type:'string',minLength:1},description:'Concrete observations or saved outputs requested from this child. Required by managed research admission; optional for generic delegation.'}},
      }}},
    },
    async execute(toolCallId, params, signal) {
      const jobs = validateTasks(params, maxTasks);
      validateDelegationGraph(jobs);
      const reviewing=Object.hasOwn(params,'review_products');
      if(Object.hasOwn(params,'review_source_refs')&&(!reviewing||!Array.isArray(params.review_source_refs)||
        params.review_source_refs.some(value=>!nonempty(value))||new Set(params.review_source_refs).size!==params.review_source_refs.length))throw new TypeError('Invalid review source selection');
      if(reviewing&&(!prepareReview||!Array.isArray(params.review_products)||!params.review_products.length||
        params.review_products.some(path=>!nonempty(path))||new Set(params.review_products).size!==params.review_products.length))throw new TypeError('Invalid or unavailable delivery review selection');
      // Admission is one whole-batch decision before any worker starts. The
      // host validates managed research scope; generic callers need no cycle.
      const reviewPacket=reviewing?freeze(await prepareReview([...params.review_products],{jobs,signal,source_refs:params.review_source_refs??[]})):undefined;
      const binding=admitTasks===undefined?undefined:checkedBinding(await admitTasks(jobs,{toolCallId,signal,...(reviewPacket?{reviewMode:'delivery'}:{})}));
      const children = new Array(jobs.length);
      const worker = async (job,dependencyResults) => {
          const index = jobs.indexOf(job);
          const source = Object.freeze({kind: 'native_subagent', id: job.id, title: job.title});
          const observations = [];
          const notify = (type, extra = {}) => emit?.(freeze({type,...extra,subordinate:true,
            parent_tool_call_id:toolCallId,child_id:job.id,title:job.title,...binding,...(reviewPacket?{review_mode:'delivery'}:{}),
            questions:[...(job.questions??[])],expected_outputs:[...(job.expected_outputs??[])]}));
          if (signal?.aborted) {
            children[index] = {source, status: 'cancelled', answer: '', usage: [],
              model_responses: 0, turns: 0,
              error: {code: 'child_not_started', message: 'Parent cancellation prevented child execution.'}};
            return children[index];
          }
          try {
            notify('delegation_child_started');
            const result = await runChild(job, {
              signal,
              dependencyResults:freeze(structuredClone(dependencyResults)),
              siblingTasks: freeze(jobs.filter(item => item.id !== job.id).map(item => ({id:item.id,title:item.title,
                questions:[...(item.questions??[])],expected_outputs:[...(item.expected_outputs??[])]}))),
              ...(reviewPacket?{reviewPacket}:{}),
              onToolActivity: event => {if(reviewPacket)throw new TypeError('Delivery review is read-only text inspection and cannot execute child tools');return notify('delegation_child_tool', {
                activity: event.type, tool_name: event.toolName,
                ...(event.args !== undefined ? {args: event.args} : {}),
                ...(event.result !== undefined ? {result: event.result} : {}),
                ...(typeof event.toolCallId === 'string' ? {tool_call_id: event.toolCallId} : {}),
                ...(typeof event.isError === 'boolean' ? {is_error: event.isError} : {}),
              });},
              onAssistantUsage: usage => { observations.push(actualUsage(usage)); },
              onModelResponse: timing => notify('delegation_child_response', timing),
              // Child text is returned as a labelled outcome, not interleaved
              // with the parent's answer or exposed as parent progress.
              onTextDelta: () => {},
              onTurnEnd: () => {},
            });
            if (!result || typeof result.responseText !== 'string'
                || (result.failure !== undefined && typeof result.failure !== 'string')
                || (result.usage !== undefined && !Array.isArray(result.usage))) {
              throw new TypeError('Invalid child result');
            }
            const usage = Array.isArray(result.usage) ? result.usage.map(actualUsage) : observations;
            const cancelled = result.aborted === true || signal?.aborted === true;
            const empty = !result.responseText.trim();
            const status = cancelled ? 'cancelled' : result.failure || empty ? 'failed' : 'completed';
            children[index] = {source, status, answer: result.responseText, usage,
              ...(result.finish?{finish:checkedFinish(result.finish)}:{}),
              ...(cancelled ? {error: {code: 'child_cancelled', message: 'Child execution was cancelled.'}}
                : result.failure ? {error: {code: result.failure_code==='model_output_limit'?'model_output_limit':'child_failed', message: result.failure}}
                  : empty ? {error: {code: 'empty_child_output', message: 'Child returned no answer.'}} : {}),
              ...(Number.isSafeInteger(result.turns) && result.turns >= 0 ? {turns: result.turns} : {}),
              ...(Number.isSafeInteger(result.modelResponses) && result.modelResponses >= 0
                ? {model_responses: result.modelResponses} : {}),
            };
          } catch (error) {
            const cancelled = signal?.aborted === true || error?.name === 'AbortError';
            const type = ['Error', 'TypeError', 'RangeError', 'AbortError'].includes(error?.name) ? error.name : 'Error';
            children[index] = {source, status: cancelled ? 'cancelled' : 'failed', answer: '', usage: observations,
              error: {code: cancelled ? 'child_cancelled' : 'child_execution_failed', type,
                message: cancelled ? 'Child execution was cancelled.' : 'Child execution failed. Inspect protected child diagnostics.'}};
          }
          notify('delegation_child_finished', {status:children[index].status,result_summary:children[index].answer,
            ...(children[index].error?{error:{...children[index].error}}:{})});
          return children[index];
      };
      // A host receipt error must not release the tool while sibling sessions
      // still run. Each runChild settles only after its own child cleanup.
      await scheduleDelegation({jobs,concurrency,signal,run:worker,onNotStarted:(job,result)=>{
        children[jobs.indexOf(job)]={source:{kind:'native_subagent',id:job.id,title:job.title},
          status:result.status==='blocked'?'failed':'cancelled',answer:'',usage:[],model_responses:0,turns:0,
          error:{code:result.status==='blocked'?'child_dependency_failed':'child_not_started',
            message:result.status==='blocked'?'A required child did not complete. This task did not start.':'Parent cancellation prevented child execution.'},
          blocked_by:result.blocked_by};
      }});
      const details = {schema: 'capstone-delegation-result/1', scope: 'instruction',
        authority_evidence: false, children, usage: aggregateUsage(children)};
      if(reviewPacket){
        details.review_packet={fingerprint:reviewPacket.fingerprint??null,documents:reviewPacket.documents.length,
          supplied_chars:reviewPacket.documents.reduce((sum,item)=>sum+Array.from(item.text).length,0),
          source_selection:reviewPacket.source_selection??null};
        try{details.delivery_review=completeDeliveryReview(reviewPacket,children);}
        catch{details.review_error={code:'delivery_review_unavailable',message:'Independent review was incomplete, cancelled, failed, or did not return valid findings. Saved products remain available. Check the actual child finish reason and packet fingerprint; an unchanged packet repeats the same workload. Change relevant source scope or configured model/output budget, or report the review limitation.'};}
      }
      return {content: [{type: 'text', text: JSON.stringify(details)}], details,
        isError: Boolean(details.review_error)||!children.some(child => child.status === 'completed')};
    },
  };
}
