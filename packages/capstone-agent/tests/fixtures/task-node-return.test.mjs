import test from 'node:test';
import assert from 'node:assert/strict';
const {createTaskNodeReturn}=await import('../../src/capstone_agent/resources/task-node-return.mjs').catch(e=>{
  if(e.code==='ERR_MODULE_NOT_FOUND')return {};throw e;
});
const action={id:'action-A',definition_ref:'definition-A',execution_revision:2,
  input_bindings:[{input_name:'prior',result_ref:'result-A'}],source_versions:[{ref:'source-A',revision:'v1'}]};
const node={purpose:'One question',instruction:'Use selected facts',questions:['What follows?'],
  outputs:[{slot:'answer',kind:'artifact',description:'Useful answer'}],checks:['Inspect actual output']};
const inputs={manifests:[{result_ref:'result-A',summary:'Prior finding',scope:'Selected scope',
  observation_refs:['obs-prior'],artifact_refs:[],source_versions:[{ref:'source-A',revision:'v1'}]}],handles:[]};
test('selected files retain descriptive host metadata beside the exact read-only handle',()=>{
  const handle={ref:'product-1',result_ref:'result-A',path:'/sealed/opaque',read_only:true,immutable:true,
    file_name:'图表.png',media_type:'image/png',size_bytes:123,sha256:'a'.repeat(64),roles:['support'],output_slot:'figure'};
  const granted={manifests:[{...inputs.manifests[0],artifact_refs:['product-1']}],handles:[handle]};
  const file=createTaskNodeReturn(action,node,granted).assignment.inputs[0].files[0];
  assert.equal(file.path,handle.path);assert.equal(file.read_only,true);
  for(const key of ['file_name','media_type','size_bytes','sha256','roles','output_slot'])assert.deepEqual(file[key],handle[key]);
  file.roles.push('changed');assert.deepEqual(handle.roles,['support']);
});
const value=()=>({schema:'capstone-task-return/1',outputs:[{slot:'answer',summary:'Observed answer',scope:'Assigned inputs',
  observations:['o1','i1'],files:[{path:'answer.md',role:'primary'}]}],
  checks:[{check:1,status:'passed',observations:['o1'],explanation:'Read the saved file'}],limitations:[]});
test('advisory submission retains usable output and records malformed checks without a repair loop',()=>{
  const adapter=createTaskNodeReturn(action,node,inputs,{advisoryChecks:true});
  const request={summary:'Usable result',outputs:[{slot:'answer',files:[{path:'answer.md',role:'primary'}]}],
    checks:[{check:999,status:'passed',explanation:'Unbound check'},{check:1,status:'pass',explanation:''}]};
  const submitted=adapter.submission(request,'submission-observation'),result=adapter.normalize(submitted);
  assert.equal(result.products[0].path,'answer.md');
  assert.equal(result.proposal.checks[0].status,'not_run');
  assert.ok(result.proposal.limitations.some(note=>note.includes('Invalid advisory check')));
  assert.throws(()=>createTaskNodeReturn(action,node,inputs).submission(request,'submission-observation'),/invalid check/);
});
test('structured submissions leave identity, scope and unchecked status to the host',()=>{
  const adapter=createTaskNodeReturn(action,node,inputs);
  const submitted=adapter.submission({summary:'A useful "quoted" finding\n第二行',outputs:[{slot:'answer',files:[{path:'answer.md',role:'primary'}]}],
    limitations:['Analytical review remains open']},'submission-observation');
  adapter.observe('submission-observation');const result=adapter.normalize(submitted);
  assert.equal(submitted.outputs[0].summary,'A useful "quoted" finding\n第二行');
  assert.deepEqual(result.proposal.outputs[0].observation_refs,['submission-observation']);
  assert.equal(result.proposal.checks[0].status,'not_run');
  assert.deepEqual(result.proposal.checks[0].refs,[]);
  assert.match(submitted.outputs[0].scope,/producer statement/i);
  assert.throws(()=>adapter.submission({summary:'Saved',outputs:[{slot:'answer',files:[{path:'../foreign',role:'primary'}]}]},'submission-observation'),/file path/);
});
test('a saved producer statement survives unknown support without inventing verification',()=>{
  const adapter=createTaskNodeReturn(action,{...node,outputs:[{slot:'answer',kind:'observation',description:'Finding'}]},inputs);
  const submitted=adapter.submission({summary:'Calculated result',outputs:[{slot:'answer',observations:['unknown-support']}],
    checks:[{check:1,status:'passed',observations:['unknown-support'],explanation:'Producer claims checked'}]},'submission-observation');
  assert.deepEqual(adapter.normalize(submitted).proposal.outputs[0].observation_refs,[],
    'The submission receipt is not admitted before actual tool completion');
  adapter.observe('submission-observation');
  const result=adapter.normalize(submitted);
  assert.deepEqual(result.proposal.outputs[0].observation_refs,['submission-observation']);
  assert.match(result.proposal.outputs[0].scope,/producer statement/i);
  assert.match(result.proposal.limitations.join('\n'),/unverified/);
  assert.equal(result.proposal.checks[0].status,'not_run');
  assert.deepEqual(result.proposal.checks[0].refs,[]);
  assert.doesNotMatch(JSON.stringify(result),/unknown-support/);
});
test('a consumer receives the selected producer limitations as well as inherited limitations',()=>{
  const direct={result_ref:'result-A',assessment_ref:'assessment-A',record_limitations:['Review incomplete']};
  const inherited={result_ref:'older',assessment_ref:'assessment-older',record_limitations:['Earlier gap']};
  const bound={...action,input_bindings:[{...action.input_bindings[0],accepted_limitations:direct}]};
  const granted={...inputs,manifests:[{...inputs.manifests[0],input_limitations:[inherited]}]};
  const adapter=createTaskNodeReturn(bound,node,granted);
  assert.deepEqual(adapter.assignment.inputs[0].input_limitations,[inherited,direct]);
  adapter.assignment.inputs[0].input_limitations[1].record_limitations.push('Local edit');
  assert.deepEqual(direct.record_limitations,['Review incomplete']);
});
test('compact node return binds local aliases and numbered checks without model-written identity',()=>{
  assert.equal(typeof createTaskNodeReturn,'function');
  const adapter=createTaskNodeReturn(action,node,inputs);
  assert.equal(adapter.observe('obs-now'),'o1');assert.equal(adapter.observe('obs-now'),'o1');
  const result=adapter.normalize(value());
  assert.deepEqual(result.products,[{path:'answer.md',role:'primary'}]);
  assert.deepEqual(result.proposal.binding,{action_id:'action-A',definition_ref:'definition-A',execution_revision:2,
    consumed_results:['result-A'],source_versions:[{ref:'source-A',revision:'v1'}]});
  assert.deepEqual(result.proposal.outputs[0].observation_refs,['obs-now','obs-prior']);
  assert.equal(result.proposal.checks[0].description,'Inspect actual output');
  assert.doesNotMatch(JSON.stringify(adapter.assignment),/source_versions|definition_ref|execution_revision/);
  assert.equal(adapter.assignment.inputs[0].summary,'Prior finding');
});
test('compact returns reject foreign identities, unsafe paths and changed declarations before admission',()=>{
  const adapter=createTaskNodeReturn(action,node,inputs);adapter.observe('obs-now');
  for(const mutate of [v=>v.binding={},
    v=>v.checks[0].check=2,v=>v.checks.push(v.checks[0]),v=>v.outputs.push(v.outputs[0]),
    v=>v.outputs[0].files[0].path='../foreign.md']){
    const v=value();mutate(v);assert.throws(()=>adapter.normalize(v),/Task return/);
  }
  const other=createTaskNodeReturn(action,node,inputs);
  assert.deepEqual(other.normalize(value()).proposal.outputs[0].observation_refs,['obs-prior']);
});
test('incomplete declared work retains supplied outputs and supplies honest missing checks',()=>{
  const adapter=createTaskNodeReturn(action,{...node,outputs:[...node.outputs,{slot:'extra',kind:'artifact',description:'Optional follow-up'}],
    checks:[...node.checks,'Compare extra output']},inputs);adapter.observe('obs-now');
  const result=adapter.normalize(value());
  assert.equal(result.proposal.outputs.length,1);
  assert.equal(result.proposal.checks[1].status,'not_run');
  assert.deepEqual(result.proposal.checks[1].refs,[]);
  assert.match(result.proposal.limitations.join('\n'),/extra/);
  assert.match(result.proposal.limitations.join('\n'),/Compare extra output/);
});
test('exact admitted references remain valid without an alias-only repair',()=>{
  const adapter=createTaskNodeReturn(action,node,inputs);adapter.observe('obs-now');
  const v=value();v.outputs[0].observations=['obs-now','obs-prior'];v.checks[0].observations=['obs-now'];
  const result=adapter.normalize(v);
  assert.deepEqual(result.proposal.outputs[0].observation_refs,['obs-now','obs-prior']);
  assert.deepEqual(result.proposal.checks[0].refs,['obs-now']);
});
test('unknown support preserves findings and files with an explicit limitation',()=>{
  const adapter=createTaskNodeReturn(action,node,inputs);adapter.observe('obs-now');
  const v=value();v.outputs[0].observations=['o1','o99'];
  const result=adapter.normalize(v);
  assert.deepEqual(result.proposal.outputs[0].observation_refs,['obs-now']);
  assert.equal(result.proposal.outputs[0].summary,v.outputs[0].summary);
  assert.deepEqual(result.products,v.outputs[0].files);
  assert.match(result.proposal.limitations.join('\n'),/outputs\[0\].*unverified/);
});
test('unsupported passed checks retain the producer explanation without claiming a supported pass',()=>{
  const adapter=createTaskNodeReturn(action,node,inputs);adapter.observe('obs-now');
  const v=value();v.checks[0].observations=['obs-foreign'];
  const result=adapter.normalize(v);
  assert.equal(result.proposal.checks[0].status,'not_run');
  assert.deepEqual(result.proposal.checks[0].refs,[]);
  assert.match(result.proposal.checks[0].explanation,/Producer reported passed/);
  assert.match(result.proposal.checks[0].explanation,/Read the saved file/);
  assert.doesNotMatch(JSON.stringify(result),/obs-foreign/);
});
test('observation-only discovery returns no artifact and preserves honest not-run checks',()=>{
  const adapter=createTaskNodeReturn(action,{...node,outputs:[{slot:'answer',kind:'observation',description:'Decision facts'}]},inputs);
  const v=value();v.outputs[0].observations=['i1'];v.outputs[0].files=[];
  v.checks[0]={check:1,status:'not_run',observations:[],explanation:'Artifact check not performed'};
  const result=adapter.normalize(v);assert.deepEqual(result.products,[]);
  assert.equal(result.proposal.checks[0].status,'not_run');assert.deepEqual(result.proposal.checks[0].refs,[]);
});
test('adapter freezes host binding and retains conflicting presentation roles conservatively',()=>{
  const a=structuredClone(action),n={...node,outputs:[...node.outputs,{slot:'second',kind:'artifact',description:'Second use'}]};
  const adapter=createTaskNodeReturn(a,n,inputs);adapter.observe('obs-now');a.execution_revision=99;
  const v=value();v.outputs.push({...v.outputs[0],slot:'second'});
  assert.equal(adapter.normalize(v).proposal.binding.execution_revision,2);
  v.outputs[1]={...v.outputs[1],files:[{path:'answer.md',role:'support'}]};
  const result=adapter.normalize(v);
  assert.equal(result.products[0].role,'support');
  assert.match(result.proposal.limitations.join('\n'),/role/);
});
test('presentation role spelling never discards a saved analysis file',()=>{
  const adapter=createTaskNodeReturn(action,node,inputs);adapter.observe('obs-now');
  const v=value();v.outputs[0].files[0].role='data';
  const result=adapter.normalize(v);
  assert.deepEqual(result.products,[{path:'answer.md',role:'support'}]);
  assert.match(result.proposal.limitations.join('\n'),/role/);
  delete v.outputs[0].files[0].role;
  assert.equal(adapter.normalize(v).products[0].role,'support');
});

test('completion merges duplicate declared slots and records undeclared associations without resubmission',()=>{
  const adapter=createTaskNodeReturn(action,node,inputs);
  const result=adapter.submission({summary:'Actual return',outputs:[
    {slot:'answer',files:[{path:'first.md',role:'primary'}]},
    {slot:'answer',files:[{path:'second.md',role:'support'}]},
    {slot:'unknown',summary:'Unbound producer statement'}]},'receipt');
  assert.equal(result.outputs.length,1);
  assert.equal(result.outputs[0].files.length,2);
  assert.ok(result.limitations.some(note=>note.includes('Unbound')));
});
