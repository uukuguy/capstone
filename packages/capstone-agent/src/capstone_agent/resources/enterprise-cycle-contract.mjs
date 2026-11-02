/** Enterprise tool contract. The host CAS adapter owns revision and replay. */
import {validateDelegationGraph} from './delegation-scheduler.mjs';
const text={type:'string',minLength:1};
const recordId={type:'string',minLength:1,maxLength:128,pattern:'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$'};
const texts={type:'array',items:text};
const enumeration=(...values)=>({type:'string',enum:values});
const object=(properties,optional=[])=>({type:'object',additionalProperties:false,properties,required:Object.keys(properties).filter(key=>!optional.includes(key))});
const array=items=>({type:'array',items});
const described=(schema,description)=>({...schema,description});
const references=description=>described(texts,description+' Copy exact host-admitted reference strings. Do not invent IDs, file names, or evidence. Use [] if no admitted references apply.');
const actionId=described(text,'Copy the exact current pending_action.id from the preceding successful cycle result. Record uses an execute action; assess uses its separate assess action.');
const objective=object({
  id:described(recordId,'Choose a stable unique objective ID, such as source-profile. Use this exact ID in dependencies and coverage; a purpose, file name, source reference or question is not an objective ID.'),
  purpose:described(text,'Business purpose of this bounded objective. Many tool calls may serve one objective.'),
  questions:described(texts,'Concrete questions this objective must answer. Put question text here, not in depends_on or resolves.'),
  depends_on:described(texts,'Array of exact objective.id values declared in this plan or already accepted cycle. Each dependency must be satisfied before this objective runs. Use [] for independent or first work; never null or a source reference. Forward references to IDs in this plan are allowed.'),
  expected_outputs:described(texts,'Array of nonempty strings describing useful text, calculations or saved products required from this objective. Even one output uses an array, for example ["Source summary"], never a single string.'),
  checks:described(texts,'Choose explicit completion-check labels. Later assess.checks[].description must copy each label exactly, without paraphrasing. A passed check needs an actual admitted observation reference. Use [] only if no checks apply.'),
  mode:described(enumeration('execute','synthesis'),'execute requires actual host-receipted tool work. synthesis can combine already admitted inputs without a fresh tool call, but requires nonempty input_refs and useful findings or inspected products.'),
  input_refs:references('Existing admitted inputs for this objective; synthesis requires at least one.'),
  resolves:described(texts,'For operation=plan this MUST be []. Only assess.follow_ups may use this field: copy exact IDs of previously assessed partial, failed or limited objectives that this repair will resolve. This is NOT a list of questions or requirements. Do not also depend_on an unresolved target.'),
  derived_from:described(texts,'Optional exact IDs of findings already committed by record.findings[].id in this cycle that motivated these questions. Not source refs or invented findings. For initial plan omit or use [].'),
  product_paths:described(texts,'Optional exact private workspace-relative paths of this producer objective\'s requested core files. Declare final report/table paths, not temporary scripts, optional checker logs or perfect-validation requirements. With the host draft protocol, once all these files are actually observed, record their versions before more native work. This records bytes, not quality. Put advisory checks in a separate objective; handoff can depend on production without requiring advisory checks to pass.'),
  subtasks:described(array(object({id:recordId,title:text,instruction:text,questions:texts,expected_outputs:texts,depends_on:texts})),
    'Optional accepted child task graph. The host automatically dispatches it when this execute objective becomes active, without another agent_delegate call. Each question must be copied from this objective.questions. Independent nodes use depends_on: []; dependent nodes reference IDs in this same subtasks array. Return findings for parent assessment; shared final products remain parent-owned.'),
},['derived_from','product_paths','subtasks']);
export const cycleToolParameters={oneOf:[
  object({operation:{const:'plan',type:'string'},goal:text,
    output_mode:described(enumeration('text','files'),'files requires actual inspected saved outputs for final delivery; text does not require an unnecessary file.'),
    objectives:described(array(objective),'Commit a short concrete plan before executing tools. Every initial objective has resolves: [].'),
    source_refs:references('Sources already admitted by the host at planning time; reading new sources may be the first objective, so [] is allowed.')}),
  object({operation:{const:'record',type:'string'},action_id:actionId,
    outcome:described(enumeration('completed','limited','failed'),'Actual settled execution outcome. Limited or failed work requires explicit limitations, not a fabricated successful receipt.'),
    findings:array(object({id:described(text,'Stable finding ID. To revise a retained finding, use a new ID and keep the earlier provenance.'),text,
      status:described(enumeration('hypothesis','supported','refuted'),'Supported and refuted findings require successful host-admitted source refs. Keep unsupported findings as hypotheses.'),
      refs:references('Sources supporting this finding.')})),
    product_refs:described(texts,'Actual workspace-relative file paths of saved outputs to inspect, for example reports/analysis.html. Do not pass returned workspace-product hashes here. Use [] for text-only work. Returned product refs identify immutable inspected versions.'),
    limitations:described(texts,'Observed failures, missing inputs and unresolved limits. Must be nonempty for limited or failed outcomes.')}),
  object({operation:{const:'assess',type:'string'},action_id:actionId,
    coverage:described(array(object({
      objective_id:described(text,'Copy current pending_action.objective_id exactly. Assess the one active objective; do not substitute a purpose or a file name.'),
      status:described(enumeration('met','partial','unmet'),'met requires completed recorded work, observed support and all accepted objective checks passed. Use partial or unmet for unresolved work.'),
      refs:references('Observed support or diagnostic references for coverage.'),explanation:text})), 'Exactly one coverage entry for the current assessment objective.'),
    checks:array(object({
      description:described(text,'Copy an accepted objective.checks label exactly, without paraphrasing. The current pending_action.checks array contains those labels.'),
      status:described(enumeration('passed','failed','not_run'),'Use passed only with an actual successful admitted observation. A self-assessment or a file name alone is not proof.'),
      refs:references('Actual observations for this check; passed requires at least one successful reference.'),explanation:text})),
    decision:described(enumeration('continue','revise','deliver','limited','blocked'),'continue selects ready remaining work or concrete follow-ups; revise requires repair follow-ups. deliver requires every objective satisfied and current saved outputs inspected. limited or blocked preserves usable work and explains gaps.'),
    summary:described(text,'Required top-level nonempty string describing the observed result of this assessment. Place it beside decision, not inside reflection. Preserved separately as result_summary, not a replacement objective title.'),
    follow_ups:described(array(objective),'New concrete objectives only for continue or revise. Use resolves with exact old incomplete objective IDs for repairs. Newly accepted research questions take priority over older ready work. Other decisions require [].'),
    delivery_product_refs:described(texts,'Optional only for deliver or limited: actual workspace-relative paths selecting the final deliverable set from previously recorded inspected products. Process products stay retained; listing a path does not prove quality. Select all requested deliverables and their intended supporting outputs; omit unrelated intermediate research files. Omission preserves the existing accepted scope, or legacy all-active scope when none was selected.'),
    reflection:object({
      discoveries:described(texts,'IDs of already committed findings relevant to this assessment. This records discoveries, not new unsupported facts.'),
      unresolved_questions:array(object({question:text,derived_from:described(texts,'Exact IDs of committed findings that prompted this open question; [] if none.')})),
      contradictions:array(object({finding_ids:described(texts,'IDs of committed findings whose conflict needs resolution.'),summary:text})),
      next_step_reason:described(text,'Concise public reason why the observed findings, gaps or contradictions require the selected next action; not private reasoning.'),
    },['discoveries','unresolved_questions','contradictions','next_step_reason']),
    supersedes:described(array(object({objective_id:recordId,reason:text,replacement_ids:texts})),
      'Only continue/revise: replace an old pending, never executed objective with one or more new follow_ups IDs. Give the observed reason. Old history remains; its dependants wait for all replacements. Do not supersede completed or active work, invent IDs, or create dependency cycles.'),
    question_adoptions:described(array(object({
      objective_id:described(recordId,'Exact ID of an existing pending objective. Active, assessed, completed and superseded objectives cannot be changed.'),
      questions:described(texts,'Nonempty new questions to append to this pending objective. Existing or repeated question strings are deduplicated; do not restate the whole plan.'),
      derived_from:described(texts,'Nonempty IDs of already committed findings that motivate these questions. Every referenced finding must carry successful host-admitted source observations; an unsupported hypothesis is not sufficient.'),
    })),'Only continue/revise: turn an observed discovery or reflected open question into accepted future work without inventing another objective. Questions and their finding provenance are committed before activation. Use follow_ups instead when the work needs a new objective.'),
  },['reflection','supersedes','question_adoptions','delivery_product_refs']),
]};
// SDK/provider function tools expect an object root. Branch constraints keep
// mutually exclusive operations strict; the root exposes the complete field
// vocabulary without requiring fields belonging to a different operation.
cycleToolParameters.type='object';
cycleToolParameters.additionalProperties=false;
cycleToolParameters.required=['operation'];
cycleToolParameters.properties=Object.assign({},...cycleToolParameters.oneOf.map(branch=>branch.properties),
  {operation:enumeration('plan','record','assess')});

// Public split entrances derive from the canonical operation contracts. The
// caller cannot select or override the operation bound by the registered tool.
export const cycleOperationToolParameters=Object.fromEntries(cycleToolParameters.oneOf.map(branch=>{
  const schema=structuredClone(branch),operation=schema.properties.operation.const;
  delete schema.properties.operation;
  schema.required=schema.required.filter(name=>name!=='operation');
  return [operation,schema];
}));

export class EnterpriseCycleError extends Error {
  constructor(code,message){super(message);this.name='EnterpriseCycleError';this.code=code;}
}
export function requireCycle(condition,message,code='invalid_enterprise_cycle') {
  if(!condition)throw new EnterpriseCycleError(code,message);
}
/** Small dependency-free validator for the JSON subset used by this contract. */
function validate(value,schema,path='operation') {
  if(schema.const!==undefined)requireCycle(value===schema.const,`${path}: invalid operation`);
  if(schema.enum)requireCycle(schema.enum.includes(value),`${path}: choose a published enum value`);
  if(schema.type==='string')requireCycle(typeof value==='string'&&value.trim().length>0,`${path}: expected nonempty text`);
  if(schema.pattern)requireCycle(new RegExp(schema.pattern).test(value),`${path}: use a valid objective ID with letters, digits, underscores, dots or hyphens`);
  if(schema.type==='array') {
    requireCycle(Array.isArray(value),`${path}: expected array; use [] for none, never null`);
    value.forEach((item,index)=>validate(item,schema.items,`${path}[${index}]`));
  }
  if(schema.type==='object') {
    requireCycle(value!==null&&typeof value==='object'&&!Array.isArray(value)&&Object.getPrototypeOf(value)===Object.prototype,'Expected plain object');
    requireCycle(Object.keys(value).every(key=>Object.hasOwn(schema.properties,key))&&schema.required.every(key=>Object.hasOwn(value,key)),'Unexpected or missing operation fields');
    for(const [key,child] of Object.entries(schema.properties))if(Object.hasOwn(value,key))validate(value[key],child,path==='operation'?key:`${path}.${key}`);
  }
}
export function validateCycleOperation(value) {
  const schema=cycleToolParameters.oneOf.find(item=>item.properties.operation.const===value?.operation);
  requireCycle(schema,'Unknown cycle operation');validate(value,schema);
  for(const item of value.objectives??value.follow_ups??[])if(item.subtasks?.length){
    requireCycle(item.mode==='execute'&&!item.product_paths?.length,'Subtasks require an execute investigation, not shared final product production');
    try{validateDelegationGraph(item.subtasks);}catch(error){throw new EnterpriseCycleError('invalid_enterprise_cycle',error.message);}
    for(const task of item.subtasks)requireCycle(task.questions.length>0&&task.expected_outputs.length>0&&
      task.questions.every(question=>item.questions.includes(question)),'Subtask questions must belong to the accepted objective and have expected outputs');
  }
  for(const item of value.objectives??value.follow_ups??[])if(item.product_paths!==undefined){
    requireCycle(item.product_paths.length>0&&new Set(item.product_paths).size===item.product_paths.length,
      'Producer product_paths must be nonempty and unique');
    requireCycle(item.product_paths.every(path=>!/[\\\x00-\x1f\x7f:]/.test(path)&&
      path.split('/').every(part=>part&&part!=='.'&&part!=='..')),
      'Producer product_paths must be exact private workspace-relative paths without traversal');
  }
  return structuredClone(value);
}
export function validateBoundCycleOperation(operation,value) {
  const schema=cycleOperationToolParameters[operation];
  requireCycle(schema,'Unknown bound cycle operation');
  validate(value,schema);
  return validateCycleOperation({...value,operation});
}
