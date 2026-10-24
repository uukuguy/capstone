/**
 * Adapted from pi-deep-research ResearchStateMachine, MIT (see LICENSE).
 * Source and adaptation notes: UPSTREAM.md. No tools, network, model or ledger
 * are created here. The caller supplies all execution and persistence ports.
 */
import {ResearchStateMachine} from './upstream/runtime/state-machine.mjs';
import {runtimeLimits,CapacityExceeded} from '../runtime-limits.mjs';
export {ResearchStateMachine as UpstreamResearchStateMachine} from './upstream/runtime/state-machine.mjs';
export {executeResearchRound as executeUpstreamResearchRound} from './upstream/runtime/research-round.mjs';
export {ProfileResolver as UpstreamProfileResolver} from './upstream/runtime/profile-resolver.mjs';
const SCHEMA = 'capability-research-runtime/1';
const PHASES = new Set(['searching', 'extracting', 'questioning', 'drafting', 'saving', 'done']);
const OPTION_KEYS=new Set(['maxRounds','maxFindings','maxQuestions','snapshotBytes','timeoutMs']);

export class ResearchRuntimeError extends Error {
  constructor(code, message) { super(message); this.name='ResearchRuntimeError'; this.code=code; }
}
function requireValue(valid, message) {
  if (!valid) throw new ResearchRuntimeError('invalid_research_runtime', message);
}
function text(value) { return typeof value==='string' && value.trim().length>0; }
function strings(value) { return Array.isArray(value) && value.every(text); }
function jsonCopy(value) {
  function check(item) {
    if (item===null || typeof item==='string' || typeof item==='boolean' ||
        (typeof item==='number' && Number.isFinite(item))) return;
    requireValue(item && typeof item==='object' &&
      (Array.isArray(item) || Object.getPrototypeOf(item)===Object.prototype), 'Expected serializable JSON');
    for (const child of Object.values(item)) check(child);
  }
  check(value);
  return structuredClone(value);
}
function budget(actual, maximum, dimension, mode='normal') {
  if (actual>maximum) {
    if(mode==='debug')throw new CapacityExceeded({[dimension]:maximum},dimension,actual,
      dimension.endsWith('_bytes')?'bytes':'items','research_runtime',{mode});
    const error=new ResearchRuntimeError('research_capacity_exceeded', `${dimension}: ${actual} exceeds ${maximum}`);
    error.capacity={dimension,actual,limit:maximum}; throw error;
  }
}
function checkedOptions(options={}) {
  const {runtimeLimits:overrides,runtimeLimitMode:mode='normal',...direct}=options;
  requireValue(Object.keys(direct).every(key=>OPTION_KEYS.has(key)),'Unknown research runtime capacity');
  const registry=runtimeLimits(overrides,{mode});
  const value={maxRounds:registry.research_round_count,maxFindings:registry.research_finding_count,
    maxQuestions:registry.research_question_count,snapshotBytes:registry.research_snapshot_bytes,
    timeoutMs:registry.tool_timeout_seconds*1000,...direct};
  for (const [key,limit] of Object.entries(value)) requireValue(Number.isSafeInteger(limit)&&limit>0,`Invalid capacity ${key}`);
  value.runtimeLimitMode=mode;
  return Object.freeze(value);
}
function checkedSnapshot(value, limits) {
  const state=jsonCopy(value);
  requireValue(state.schema===SCHEMA,'Invalid research snapshot schema');
  requireValue(PHASES.has(state.phase),'Invalid research phase');
  requireValue(text(state.plan?.runId)&&text(state.plan?.goal)&&strings(state.plan?.questions)&&strings(state.plan?.sourceRefs),'Invalid research plan');
  requireValue(Number.isSafeInteger(state.round)&&state.round>=0,'Invalid research round');
  requireValue(Array.isArray(state.findings)&&strings(state.pendingQuestions),'Invalid research snapshot collections');
  budget(state.findings.length,limits.maxFindings,'research_findings',limits.runtimeLimitMode);
  budget(state.pendingQuestions.length,limits.maxQuestions,'research_questions',limits.runtimeLimitMode);
  budget(Buffer.byteLength(JSON.stringify(state)),limits.snapshotBytes,'research_snapshot_bytes',limits.runtimeLimitMode);
  return state;
}
export function serializeSnapshot(snapshot, options) {
  return JSON.stringify(checkedSnapshot(snapshot,checkedOptions(options)));
}
export function restoreSnapshot(serialized, options) {
  requireValue(typeof serialized==='string','Research snapshot must be JSON text');
  const limits=checkedOptions(options);
  budget(Buffer.byteLength(serialized),limits.snapshotBytes,'research_snapshot_bytes',limits.runtimeLimitMode);
  return checkedSnapshot(JSON.parse(serialized),checkedOptions(options));
}
function checkedRound(value) {
  const result=jsonCopy(value);
  requireValue(Array.isArray(result.findings)&&strings(result.observations)&&strings(result.limitations)&&strings(result.productRefs),'Invalid research round result');
  const ids=new Set();
  for (const finding of result.findings) {
    requireValue(text(finding.id)&&text(finding.text)&&strings(finding.refs)&&
      ['hypothesis','supported','refuted'].includes(finding.status),'Invalid research finding');
    requireValue(finding.status==='hypothesis'||finding.refs.length>0,'Supported finding requires source references');
    requireValue(!ids.has(finding.id),'Duplicate research finding identity');ids.add(finding.id);
  }
  return result;
}
function checkedAssessment(value) {
  const assessment=jsonCopy(value);
  requireValue(['continue','revise','deliver','blocked'].includes(assessment.decision)&&text(assessment.summary)&&
    strings(assessment.refs)&&strings(assessment.followUpQuestions),'Invalid research assessment');
  requireValue(!['continue','revise'].includes(assessment.decision)||assessment.followUpQuestions.length>0,
    'Continuing research requires explicit follow-up questions');
  return assessment;
}

/** Lower phase engine. Every advance returns a serializable checkpoint.
 * Searching executes work; extracting durably records it; questioning applies
 * a supplied assessment; drafting requests delivery; saving inspects real files.
 * An assessment port may validate/transform the supplied decision; it is never
 * called without one, and the runtime never starts an extra model invocation.
 */
export class ResearchRuntime {
  constructor(ports, options={}) {
    for (const key of ['executeRound','recordResult','inspectProducts']) requireValue(typeof ports?.[key]==='function',`Missing research port ${key}`);
    this.ports=Object.freeze({...ports,prompts:Object.freeze({...ports.prompts})});
    this.limits=checkedOptions(options);
  }
  init(plan) {
    return checkedSnapshot({schema:SCHEMA,phase:'searching',plan:jsonCopy(plan),round:0,
      findings:[],pendingQuestions:jsonCopy(plan.questions),actualProductRefs:[]},this.limits);
  }
  async advance(snapshot, {assessment,signal,deadline=Date.now()+this.limits.timeoutMs}={}) {
    const state=checkedSnapshot(snapshot,this.limits);
    requireValue(Number.isFinite(deadline),'Invalid research deadline');
    const controller=new AbortController();
    const combined=signal?AbortSignal.any([signal,controller.signal]):controller.signal;
    const remaining=deadline-Date.now();
    const started=Date.now();
    const timeoutReason=()=>this.limits.runtimeLimitMode==='debug'?new CapacityExceeded(
      {tool_timeout_seconds:Math.max(0,remaining)/1000},'tool_timeout_seconds',Math.max(0,Date.now()-started)/1000,
      'seconds','research_runtime',{mode:'debug'}):new DOMException('Research deadline exceeded','TimeoutError');
    if (remaining<=0) controller.abort(timeoutReason());
    const timer=remaining>0?setTimeout(()=>controller.abort(timeoutReason()),Math.min(remaining,2147483647)):null;
    const control={signal:combined,deadline};
    const call=async(fn,input)=>{
      combined.throwIfAborted();
      let abort;
      const interrupted=new Promise((_,reject)=>{
        abort=()=>reject(combined.reason);combined.addEventListener('abort',abort,{once:true});
      });
      try { const result=await Promise.race([Promise.resolve().then(()=>fn(input,control)),interrupted]);combined.throwIfAborted();return result; }
      finally {combined.removeEventListener('abort',abort);}
    };
    const output=(status,extra={})=>({status,snapshot:checkedSnapshot(state,this.limits),...extra});
    const prompt=async(name,fallback)=>{
      const value=this.ports.prompts[name]?await call(this.ports.prompts[name],jsonCopy(state)):fallback;
      requireValue(text(value),'Research prompt must be nonempty text');
      budget(Buffer.byteLength(value),this.limits.snapshotBytes,'research_prompt_bytes',this.limits.runtimeLimitMode);return value;
    };
    const record=async(kind,result)=>{
      try {
        const receipt=jsonCopy(await call(this.ports.recordResult,{kind,recordId:`${state.plan.runId}:${state.round}:${kind}`,
          snapshot:jsonCopy(state),result:jsonCopy(result)}));
        requireValue(text(receipt.checkpointRef)&&Number.isSafeInteger(receipt.revision)&&receipt.revision>=0,'Invalid committed research receipt');
        state.checkpoint=receipt;return true;
      } catch(error) {
        combined.throwIfAborted();
        // The same checkpoint/result is returned for receipt recovery. Work is
        // not repeated after an uncertain persistence outcome.
        if(error instanceof ResearchRuntimeError||error instanceof CapacityExceeded)throw error;
        return false;
      }
    };
    try {
      combined.throwIfAborted();
      const stages={
        searching:async()=>{
          if(state.round>=this.limits.maxRounds){
            if(this.limits.runtimeLimitMode==='debug')budget(state.round+1,this.limits.maxRounds,'research_rounds','debug');
            return output('limited',{reason:'round_limit'});
          }
          const result=checkedRound(await call(this.ports.executeRound,{runId:state.plan.runId,round:state.round+1,
            objective:state.plan.goal,questions:jsonCopy(state.pendingQuestions),sourceRefs:jsonCopy(state.plan.sourceRefs)}));
          state.round++;state.pendingResult=result;state.phase='extracting';
          return output('in_progress',{inject:await prompt('extraction','Inspect actual observations and record source-backed findings.')});
        },
        extracting:async()=>{
          const result=checkedRound(state.pendingResult);
          const findings=new Map(state.findings.map(item=>[item.id,item]));
          for(const finding of result.findings)findings.set(finding.id,finding);
          state.findings=[...findings.values()];
          // Check capacity before any durable write.
          checkedSnapshot(state,this.limits);
          if(!await record('round',result))return output('record_pending',{reason:'checkpoint_not_confirmed'});
          state.phase='questioning';
          return output('in_progress',{inject:await prompt('questioning','Evaluate findings and remaining work; supply continue, revise, deliver or blocked with actual references.')});
        },
        questioning:async()=>{
          if(!state.pendingAssessment) {
            if(assessment===undefined)return output('needs_assessment');
            const suppliedAssessment=checkedAssessment(assessment);
            state.pendingAssessment=this.ports.assess?checkedAssessment(await call(this.ports.assess,
              {snapshot:jsonCopy(state),result:jsonCopy(state.pendingResult),suppliedAssessment})):suppliedAssessment;
          }
          const decision=checkedAssessment(state.pendingAssessment);
          budget(decision.followUpQuestions.length,this.limits.maxQuestions,'research_questions',this.limits.runtimeLimitMode);
          if(this.limits.runtimeLimitMode==='debug'&&['continue','revise'].includes(decision.decision)&&state.round>=this.limits.maxRounds)
            budget(state.round+1,this.limits.maxRounds,'research_rounds','debug');
          if(!await record('assessment',decision))return output('record_pending',{reason:'checkpoint_not_confirmed'});
          state.lastAssessment=decision;delete state.pendingAssessment;
          if(decision.decision==='blocked')return output('blocked',{reason:'assessment_blocked'});
          if(decision.decision==='deliver')state.phase='drafting';
          else {
            state.pendingQuestions=decision.followUpQuestions;state.phase='searching';
            if(state.round>=this.limits.maxRounds)return output('limited',{reason:'round_limit'});
          }
          return output('in_progress');
        },
        drafting:async()=>{
          state.phase='saving';
          return output('in_progress',{inject:await prompt('delivery','Deliver the requested usable products; preserve existing valid files and state limitations. Completion requires actual saved products.')});
        },
        saving:async()=>{
          const inspected=jsonCopy(await call(this.ports.inspectProducts,{snapshot:jsonCopy(state),
            requested:state.plan.questions,productRefs:state.pendingResult.productRefs}));
          requireValue(typeof inspected.ready==='boolean'&&strings(inspected.actualProductRefs)&&strings(inspected.limitations),'Invalid product inspection');
          state.actualProductRefs=inspected.actualProductRefs;state.productLimitations=inspected.limitations;
          if(!inspected.ready)return output('needs_products');
          state.phase='done';return output('done');
        },
      };
      // The pinned upstream machine remains the phase driver. Ports replace
      // its environment-specific stages; without ports it retains the original
      // injected-search/extraction/follow-up/draft implementation.
      const machine=new ResearchStateMachine({ports:stages,
        searchFn:async()=>{throw new Error('Enterprise execution port is required');},
        scraper:{scrape:async()=>{throw new Error('Enterprise execution port is required');}},
        profileResolver:{resolve:()=>({breadth:this.limits.maxQuestions,depth:this.limits.maxRounds,concurrency:1})},
        logger:{event(){}},artifactsDir:'.'});
      const result=await machine.next(state,state.plan);
      return state.phase==='done'&&!result.status?output('done'):result;
    } finally {if(timer!==null)clearTimeout(timer);}
  }
}
