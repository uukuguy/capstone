import {createHash} from 'node:crypto';
import {open} from 'node:fs/promises';
import {constants} from 'node:fs';
import {isAbsolute,join} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';

export const diagnosisTools=['agent_diagnosis_record','agent_diagnosis_guide'];
const schema='capstone-systematic-diagnosis/1';
export const diagnosisGuide=`Use diagnosis for unexpected errors, conflicting results or attempts without new information.
Read retained records first. Preserve rejected hypotheses and probes after recovery.
An unfinished reserved probe has an unknown execution outcome. Recover its existing tool receipt before any repeat.
Begin with the issue, exact input_version, observed evidence_refs, one falsifiable hypothesis,
a minimal_probe using existing permitted tools, retry_reason, comparison with a working example
(or an explicit unavailable comparison), rejected_hypotheses and acceptance: advisory or objective.
Use the returned host scope_ref for a failed selection. Read with scope_ref to recover its full records.
The host reserves a finite budget for the observed issue and input scope, shared by parent and children.
Display labels cannot reset it. Without an observed scope_ref, declared probes share the task fallback budget;
model-supplied issue or input_version text cannot create a fresh host scope.
A transient failure, changed input, corrected call or new hypothesis can justify a repeated call.
Only execute the probe after a probe_reserved receipt. This tool executes no probe and grants no access.
Finish that probe_id with the actual outcome: passed, failed, not_run or unknown, outcome_refs,
information_gained, rejected_hypotheses and next_disposition: continue, change_method, retain_gap,
stop_dependent or request_input. Record failed and unperformed checks honestly.
These are reported observations, not host-certified facts or Authority evidence. Objective grid
model, solver, unit, revision and result admission remain enforced by their registered contracts.
Research checks are advisory by default: retain findings and gaps and deliver useful work.
Missing optional proof does not block delivery. A genuinely missing required input can block its dependent action.
If exhausted, keep useful work and the gap, change method, continue independent work or request required input.
Do not reset the budget by renaming an issue. Do not retry an unknown side effect: recover the exact receipt first.`;

// Hash a typed ASCII tree rather than each language's decimal JSON formatter.
// JSON numbers use IEEE 754 binary64 in the SDK. Normalize signed zero because
// JSON.stringify transmits both signs as 0. Strings/keys use exact UTF-8 bytes.
function wireString(value){
  if(/[\uD800-\uDFFF]/u.test(value))throw new TypeError('Diagnostic text contains an unpaired surrogate');
  return Buffer.from(value,'utf8').toString('hex');
}
function wireValue(value){
  if(value===null)return ['null'];
  if(typeof value==='boolean')return ['bool',value];
  if(typeof value==='string')return ['str',wireString(value)];
  if(typeof value==='number'){
    if(!Number.isFinite(value))throw new TypeError('Diagnostic numbers must be finite');
    const bytes=Buffer.alloc(8);bytes.writeDoubleBE(value===0?0:value);
    return ['num',bytes.toString('hex')];
  }
  if(Array.isArray(value))return ['array',value.map(wireValue)];
  if(value&&typeof value==='object')return ['object',Object.entries(value).map(([key,item])=>[wireString(key),wireValue(item)])
    .sort(([left],[right])=>left<right?-1:left>right?1:0)];
  throw new TypeError('Diagnostic values must be JSON data');
}
export const diagnosisDigest=value=>createHash('sha256').update(JSON.stringify(wireValue(value))).digest('hex');
const digest=diagnosisDigest;
const text={type:'string',maxLength:2000};
const texts={type:'array',maxItems:16,items:text};

// This client reads only host-owned receipts, never model-writable workspace files.
export function createDiagnosisTools(config,{emit=frame=>process.stdout.write(JSON.stringify(frame)+'\n')}={}){
  const grants=config.applicationPolicy?.allowed_tools??[];
  if(!isAbsolute(config.diagnosisContextPath??''))return [];
  const sent=new Map(),confirmed=new Map();
  async function request(callId,args,signal){
    const id='diag-'+digest({namespace:config.diagnosisNamespace??'parent',callId});
    const frame={type:'systematic_diagnosis_request',schema,request_id:id,operation:args.operation,record:args.record??{}};
    const hash=digest(frame);
    if(sent.has(id)&&sent.get(id)!==hash)throw new Error('Diagnostic request identity changed. Recover the original call.');
    if(confirmed.has(id))return confirmed.get(id);
    signal?.throwIfAborted();
    if(!sent.has(id)){sent.set(id,hash);await emit(frame);}
    const deadline=Math.min(config.deadlineAt??Infinity,Date.now()+15000);
    while(true){
      signal?.throwIfAborted();
      let file;
      try{
        file=await open(join(config.diagnosisContextPath,'responses',id+'.json'),constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);
        const info=await file.stat();
        if(!info.isFile()||info.size>524288)throw new Error('Diagnostic receipt is invalid');
        const receipt=JSON.parse(await file.readFile('utf8'));
        if(receipt.schema!==schema||receipt.request_id!==id||receipt.request_sha256!==hash)throw new Error('Diagnostic receipt identity changed');
        if(receipt.ok!==true)throw new Error('Host rejected the diagnostic record. Correct its fields; required persistence remains enforced.');
        const result={content:[{type:'text',text:JSON.stringify(receipt.result)}],details:{diagnosis:receipt.result}};
        confirmed.set(id,result);return result;
      }catch(error){if(error.code!=='ENOENT')throw error;}
      finally{await file?.close();}
      if(Date.now()>=deadline)throw new Error('Diagnostic outcome is unknown. Recover request '+id+' before executing or repeating a probe.');
      await delay(10,undefined,{signal});
    }
  }
  return [
    {name:'agent_diagnosis_guide',label:'Diagnosis guide',description:'Read the built-in systematic diagnosis method on demand.',
      parameters:{type:'object',properties:{},additionalProperties:false},
      execute:async()=>({content:[{type:'text',text:diagnosisGuide}]})},
    {name:'agent_diagnosis_record',label:'Systematic diagnosis',
      description:'Read retained diagnosis, reserve a bounded probe, or retain its actual outcome. Read agent_diagnosis_guide for fields and recovery. Never executes probes or certifies evidence.',
      parameters:{type:'object',additionalProperties:false,required:['operation'],properties:{
        operation:{type:'string',enum:['read','begin','finish']},record:{type:'object',additionalProperties:false,properties:{
          issue:text,input_version:text,evidence_refs:texts,hypothesis:text,minimal_probe:text,retry_reason:text,comparison:text,
          rejected_hypotheses:texts,acceptance:{type:'string',enum:['advisory','objective']},probe_id:text,scope_ref:text,
          outcome:{type:'string',enum:['passed','failed','not_run','unknown']},outcome_refs:texts,information_gained:text,
          next_disposition:{type:'string',enum:['continue','change_method','retain_gap','stop_dependent','request_input']}}}}},
      execute:request}
  ].filter(tool=>grants.includes(tool.name));
}
