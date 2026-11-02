import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {reduceEnterpriseCycle,readyObjectivesAfterAssessment} from '../../src/capstone_agent/resources/enterprise-cycle-state.mjs';
import {cycleToolParameters} from '../../src/capstone_agent/resources/enterprise-cycle-contract.mjs';

const limits={maxRounds:8,maxFindings:32,maxQuestions:32,snapshotBytes:100000};
const owner={thread_id:'thread-a',work_id:'work-a',research_id:'research-a',goal_revision:1};
const context=(extra={})=>({owner,attempt_id:'attempt-a',command_id:'call-a',sources:[],receipts:[],products:[],...extra});
const objective=(id='analyze',extra={})=>({id,purpose:'Analyze actual source',questions:['What changed?'],depends_on:[],
  expected_outputs:['Supported analysis'],checks:['Compare with source'],mode:'execute',input_refs:[],resolves:[],...extra});
const plan=(objectives=[objective()])=>({operation:'plan',goal:'Explain changes',output_mode:'text',objectives,source_refs:[]});
const apply=(state,command,extra={},options=limits)=>reduceEnterpriseCycle(state,command,context(extra),options);
const initialized=()=>apply(null,plan()).state;
test('limited file delivery with omitted scope cannot claim changed registered bytes',()=>{
 let state=apply(null,{...plan(),output_mode:'files'}).state;
 const saved={path:'report.md',ref:'saved',action_id:state.pending_action.id,attempt_id:'attempt-a',status:'ready'};
 state=apply(state,record(state,{product_refs:['saved']}),{receipts:[receipt(state)],products:[saved]}).state;
 const command=assessment(state,{decision:'limited',summary:'Saved report usable; independent review unavailable.',
  coverage:[{objective_id:'analyze',status:'partial',refs:['observation-a'],explanation:'Review unavailable'}],checks:[]});
 assert.throws(()=>apply(state,command,{products:[{...saved,ref:'changed'}]}),error=>error.code==='research_product_version_mismatch');
 const closed=apply(state,command,{products:[saved]}).state;
 assert.equal(closed.phase,'limited');assert.equal(closed.pending_action,null);
 assert.equal(closed.active_products[0].ref,'saved');
});
test('explicit final delivery selection preserves intermediate products without forcing them into final scope',()=>{
  let state=apply(null,{...plan(),output_mode:'files'}).state;
  const products=[{path:'data/intermediate.csv',ref:'mid-ref'},{path:'report.html',ref:'report-ref'}].map(item=>({...item,action_id:state.pending_action.id,attempt_id:'attempt-a',status:'ready'}));
  state=apply(state,record(state,{product_refs:products.map(item=>item.ref)}),{receipts:[receipt(state)],products}).state;
  const command=assessment(state,{delivery_product_refs:['report-ref']});
  const result=apply(state,command,{products:[products[1]]}).state;
  assert.deepEqual(result.delivery_products,[{path:'report.html',ref:'report-ref'}]);
  assert.equal(result.active_products.length,2);assert.equal(result.product_history.length,2);assert.equal(result.product_refs.length,2);
  assert.throws(()=>apply(state,{...command,delivery_product_refs:['invented']},{products}),/delivery|registered|inspected/i);
});
const receipt=(state,extra={})=>({ref:'observation-a',action_id:state.pending_action.id,attempt_id:'attempt-a',status:'completed',...extra});
const record=(state,extra={})=>({operation:'record',action_id:state.pending_action.id,outcome:'completed',
  findings:[{id:'finding-a',text:'Source changed',status:'supported',refs:['observation-a']}],product_refs:[],limitations:[],...extra});
const assessment=(state,extra={})=>({operation:'assess',action_id:state.pending_action.id,
  coverage:[{objective_id:state.pending_action.objective_id,status:'met',refs:['observation-a'],explanation:'Compared actual source'}],
  checks:[{description:'Compare with source',status:'passed',refs:['observation-a'],explanation:'Actual comparison'}],
  decision:'deliver',summary:'Ready',follow_ups:[],...extra});
const executed=()=>{const state=initialized();return apply(state,record(state),{receipts:[receipt(state)]}).state;};

test('ready declared investigation graphs share one host batch without weakening downstream requirements',()=>{
 const investigation=id=>objective(id,{purpose:'Investigate '+id,questions:['Question '+id],depends_on:['source'],
   subtasks:[{id:'check',title:id,instruction:'Inspect '+id,questions:['Question '+id],expected_outputs:['Finding '+id],depends_on:[]}]});
 const request=plan([objective('source',{subtasks:[]}),...['price','flow','renewable'].map(investigation),
   objective('report',{depends_on:['price','flow','renewable'],product_paths:['report.md'],subtasks:[]})]);
 const original=structuredClone(request),options={...limits,batchReadyInvestigations:true};
 let state=apply(null,request,{},options).state;
 assert.equal(state.pending_action.objective_id,'source');
 state=apply(state,record(state),{receipts:[receipt(state)]},options).state;
 const next=apply(state,assessment(state,{decision:'continue'}),{},options);
 state=next.state;const batch=state.pending_action;
 assert.match(batch.objective_id,/^host-ready-/);
 assert.equal(batch.subtasks.length,3);assert.equal(new Set(batch.subtasks.map(item=>item.id)).size,3);
 assert.deepEqual(batch.questions,['Question price','Question flow','Question renewable']);
 assert.deepEqual(batch.checks,['price: Compare with source','flow: Compare with source','renewable: Compare with source']);
 for(const id of ['price','flow','renewable']){
   const old=state.objectives.find(item=>item.id===id);
   assert.equal(old.status,'superseded');assert.deepEqual(old.supersession.replacement_ids,[batch.objective_id]);
 }
 assert.deepEqual(state.objectives.find(item=>item.id==='report').depends_on,['price','flow','renewable']);
 assert.deepEqual(next.progress_events.map(item=>item.step_id),['source',batch.objective_id]);
 state=apply(state,record(state),{receipts:[receipt(state)]},options).state;
 const checks=state.pending_action.checks.map(description=>({description,status:'passed',refs:['observation-a'],explanation:'Actual observation'}));
 state=apply(state,assessment(state,{decision:'continue',checks}),{},options).state;
 assert.equal(state.pending_action.objective_id,'report');
 assert.deepEqual(request,original,'scheduling cannot mutate the submitted plan');
 const legacy=apply(null,plan(['price','flow'].map(id=>({...investigation(id),depends_on:[]})))).state;
 assert.equal(legacy.pending_action.objective_id,'price');assert.equal(legacy.objectives.length,2);
});

test('host batching preserves an early consumer and excludes dependent or parent-owned work',()=>{
 const investigation=id=>objective(id,{subtasks:[{id:'check',title:id,instruction:'Inspect',questions:['What changed?'],expected_outputs:['Finding'],depends_on:[]}]});
 const state=apply(null,plan([investigation('price'),investigation('flow'),
   objective('price-only',{depends_on:['price'],subtasks:[]}),
   objective('report',{depends_on:['price','flow'],product_paths:['report.md'],subtasks:[]})]),{},
   {...limits,batchReadyInvestigations:true}).state;
 assert.equal(state.pending_action.objective_id,'price');
 assert.ok(!state.objectives.some(item=>item.status==='superseded'));
});

test('combined graphs keep same-named child dependencies inside their original scope',()=>{
 const tasks=[{id:'read',title:'Read',instruction:'Inspect',questions:['What changed?'],expected_outputs:['Source'],depends_on:[]},
   {id:'check',title:'Check',instruction:'Check source',questions:['What changed?'],expected_outputs:['Check'],depends_on:['read']}];
 const request=plan(['left','right'].map(id=>objective(id,{subtasks:tasks})));
 const first=apply(null,request,{}, {...limits,batchReadyInvestigations:true}).state;
 const second=apply(null,request,{}, {...limits,batchReadyInvestigations:true}).state;
 assert.deepEqual(first,second,'accepted scheduling is deterministic');
 const combined=first.pending_action.subtasks;assert.equal(new Set(combined.map(item=>item.id)).size,4);
 for(const scope of ['left','right'])assert.deepEqual(combined.find(item=>item.title===scope+': Check').depends_on,
   [combined.find(item=>item.title===scope+': Read').id]);
});

test('failed advisory check and failed repair can be recorded before independent handoff continues with warnings',()=>{
 const produce=objective('produce',{checks:['Core files saved']});
 const advisory=objective('advisory',{depends_on:['produce'],checks:['Optional consistency check']});
 const handoff=objective('handoff',{depends_on:['produce'],checks:[]});
 let state=apply(null,{...plan([produce,advisory,handoff]),output_mode:'files'}).state;
 const files=['report.html','metrics.csv'].map((path,index)=>({path,ref:'saved-'+index,action_id:state.pending_action.id,attempt_id:'attempt-a',status:'ready'}));
 state=apply(state,record(state,{findings:[],product_refs:files.map(item=>item.ref)}),{receipts:[receipt(state)],products:files}).state;
 state=apply(state,assessment(state,{decision:'continue',checks:[{description:'Core files saved',status:'passed',refs:['observation-a'],explanation:'Actual saved-file observation, not numerical quality'}]}),{products:files}).state;
 assert.equal(state.pending_action.objective_id,'advisory');
 const failures=['checker-failed','repair-failed'].map(ref=>receipt(state,{ref,status:'failed'}));
 state=apply(state,record(state,{outcome:'failed',findings:[],limitations:['Local checker failed; attempted repair failed. Existing report retained.']}),{receipts:failures,products:files}).state;
 state=apply(state,assessment(state,{decision:'continue',coverage:[{objective_id:'advisory',status:'partial',refs:[],explanation:'Check and attempted repair failed; issue retained'}],
  checks:[{description:'Optional consistency check',status:'failed',refs:['checker-failed','repair-failed'],explanation:'Actual failed execution receipts'}],summary:'Unresolved check recorded; continue independent handoff.'}),{products:files}).state;
 assert.equal(state.objectives.find(item=>item.id==='advisory').status,'partial');
 assert.equal(state.pending_action.objective_id,'handoff','continuation requires no false met verdict for the advisory objective');
 state=apply(state,record(state,{outcome:'limited',findings:[],limitations:['Draft delivered for human review; consistency issue unresolved.']}),{receipts:[receipt(state,{ref:'handoff-receipt'})],products:files}).state;
 const final=apply(state,assessment(state,{decision:'limited',coverage:[{objective_id:'handoff',status:'partial',refs:[],explanation:'Readable draft and warnings retained'}],checks:[],summary:'Human review requested with known errors.',delivery_product_refs:files.map(item=>item.ref)}),{products:files}).state;
 assert.equal(final.phase,'limited');assert.equal(final.pending_action,null);
 assert.deepEqual(final.delivery_products.map(item=>item.path),['report.html','metrics.csv']);
 assert.match(final.limitations.join('\n'),/attempted repair failed/);
 assert.equal(final.objectives.find(item=>item.id==='advisory').status,'partial');
});

test('dependency rejection identifies unresolved work without committing a failed transition',()=>{
  let state=apply(null,plan([objective(),objective('report',{depends_on:['analyze']})])).state;
  state=apply(state,record(state),{receipts:[receipt(state)]}).state;
  const before=structuredClone(state);
  assert.throws(()=>apply(state,assessment(state,{decision:'continue',
    coverage:[{objective_id:'analyze',status:'partial',refs:['observation-a'],explanation:'A source gap remains'}],
    checks:[{description:'Compare with source',status:'failed',refs:['observation-a'],explanation:'A source gap remains'}],
  })),error=>{
    assert.match(error.message,/not committed/);
    assert.match(error.message,/"id":"analyze","status":"partial"/);
    assert.match(error.message,/"id":"report","status":"pending","blocked_by":\["analyze"\]/);
    assert.match(error.message,/resolves/);return true;
  });
  assert.deepEqual(state,before);
});

test('public schema splits operations and leaves revisions to CAS adapter',()=>{
  assert.equal(cycleToolParameters.type,'object');
  assert.equal(cycleToolParameters.additionalProperties,false);
  assert.deepEqual(cycleToolParameters.required,['operation']);
  assert.equal(cycleToolParameters.oneOf.length,3);
  assert.ok(cycleToolParameters.oneOf.every(branch=>branch.additionalProperties===false));
  assert.ok(cycleToolParameters.oneOf.every(branch=>!Object.hasOwn(branch.properties,'expected_revision')));
});
test('plan is required and creates an execution action without doing work',()=>{
  assert.throws(()=>apply(null,{operation:'record',action_id:'invented'}));
  const result=apply(null,plan());
  assert.equal(result.state.phase,'executing');assert.equal(result.pending_action.kind,'execute');
  assert.equal(result.state.round,1);assert.equal(result.state.findings.length,0);
  assert.equal(result.progress.phase,'started');
});
test('no bundled assessment, and state/command inputs remain untouched',()=>{
  const state=initialized(), before=structuredClone(state),command=record(state), original=structuredClone(command);
  assert.throws(()=>apply(state,{...command,assessment:{decision:'deliver'}}));
  const result=apply(state,command,{receipts:[receipt(state)]});
  assert.deepEqual(state,before);assert.deepEqual(command,original);
  assert.equal(result.state.phase,'assessing');assert.notEqual(result.pending_action.id,state.pending_action.id);
  assert.equal(result.pending_action.kind,'assess');
  assert.throws(()=>apply(result.state,{...assessment(result.state),action_id:state.pending_action.id}));
});
test('success needs actual action-owned successful receipt',()=>{
  const state=initialized();
  for(const receipts of [[],[receipt(state,{action_id:'other'})],[receipt(state,{attempt_id:'other'})],[receipt(state,{status:'failed'})]])
    assert.throws(()=>apply(state,record(state),{receipts}));
  assert.throws(()=>apply(state,record(state),{owner:{...owner,work_id:'other'},receipts:[receipt(state)]}));
  assert.throws(()=>apply(state,record(state),{attempt_id:'attempt-b',receipts:[receipt(state)]}));
});
test('unknown finding refs and unsupported successful claim are rejected',()=>{
  const state=initialized();
  assert.throws(()=>apply(state,record(state,{findings:[{id:'f',text:'Invented',status:'supported',refs:['unknown']}]}),{receipts:[receipt(state)]}));
  assert.throws(()=>apply(state,record(state,{findings:[{id:'f',text:'Invented',status:'supported',refs:[]}]}),{receipts:[receipt(state)]}));
});
test('dependency cycles, unknown dependencies and duplicate objectives are rejected',()=>{
  for(const items of [[objective('a',{depends_on:['b']}),objective('b',{depends_on:['a']})],
    [objective('a',{depends_on:['missing']})],[objective('a'),objective('a')]])assert.throws(()=>apply(null,plan(items)));
});
test('assessment enables dependent execution and cannot deliver before coverage',()=>{
  const start=apply(null,plan([objective('a'),objective('b',{depends_on:['a']})])).state;
  const state=apply(start,record(start),{receipts:[receipt(start)]}).state;
  assert.throws(()=>apply(state,assessment(state)));
  const next=apply(state,assessment(state,{decision:'continue'}));
  assert.equal(next.state.pending_action.objective_id,'b');assert.equal(next.state.objectives[0].status,'met');
});
test('material supplementation preserves accepted findings and products',()=>{
  const start=initialized(), product={ref:'product-v1',path:'report.html',action_id:start.pending_action.id,attempt_id:'attempt-a',status:'ready'};
  const state=apply(start,record(start,{product_refs:['product-v1']}),{receipts:[receipt(start)],products:[product]}).state;
  const next=apply(state,assessment(state,{decision:'revise',coverage:[{objective_id:'analyze',status:'partial',refs:['observation-a'],explanation:'Conflict'}],
    follow_ups:[objective('repair')]}));
  assert.equal(next.pending_action.objective_id,'repair');assert.equal(next.state.findings[0].id,'finding-a');
  assert.deepEqual(next.state.product_refs,['product-v1']);assert.equal(next.state.objectives[0].status,'partial');
});
test('synthesis uses admitted existing inputs without a fabricated fresh tool call',()=>{
  const start=apply(null,plan([objective('synthesize',{mode:'synthesis',input_refs:['source-a']})]),{sources:['source-a']}).state;
  const next=apply(start,record(start,{findings:[{id:'f',text:'Synthesis',status:'supported',refs:['source-a']}]}),{sources:['source-a']});
  assert.equal(next.state.phase,'assessing');
  assert.throws(()=>apply(null,plan([objective('synthesize',{mode:'synthesis',input_refs:['unknown']})])));
});
test('failed work can be recorded honestly, then limited or blocked without erasing work',()=>{
  for(const decision of ['limited','blocked']){
    const start=initialized();const state=apply(start,record(start,{outcome:'failed',findings:[],limitations:['Source unavailable']})).state;
    const next=apply(state,assessment(state,{decision,coverage:[{objective_id:'analyze',status:'unmet',refs:[],explanation:'No source'}],
      checks:[{description:'Compare with source',status:'not_run',refs:[],explanation:'No source'}],summary:'Source unavailable'}));
    assert.equal(next.state.phase,decision);assert.equal(next.pending_action,null);assert.ok(next.state.limitations.length);
  }
});
test('delivery needs actual inspected file, coverage and applicable check observations',()=>{
  const start=apply(null,{...plan(),output_mode:'files'}).state;
  const state=apply(start,record(start),{receipts:[receipt(start)]}).state;
  assert.throws(()=>apply(state,assessment(state)));
  const text=executed();
  assert.throws(()=>apply(text,assessment(text,{checks:[]})));
  assert.throws(()=>apply(text,assessment(text,{checks:[{description:'Compare with source',status:'passed',refs:[],explanation:'Trust me'}]})));
  assert.equal(apply(text,assessment(text)).state.phase,'done');
});
test('capacity is supplied by caller, exhaustion preserves usable work',()=>{
  assert.throws(()=>reduceEnterpriseCycle(null,plan(),context()));
  assert.throws(()=>apply(null,plan(),{},{...limits,maxQuestions:0}));
  assert.throws(()=>apply(null,plan(),{},{...limits,snapshotBytes:5}),error=>error.code==='research_capacity_exceeded'&&error.capacity.unit==='bytes');
  assert.throws(()=>apply(null,plan([objective('a'),objective('b')]),{},{...limits,maxQuestions:1}),error=>error.capacity.unit==='items');
  const state=executed();
  const result=apply(state,assessment(state,{decision:'revise',follow_ups:[objective('repair')]}),{},{...limits,maxRounds:1});
  assert.equal(result.state.phase,'limited');assert.equal(result.state.findings.length,1);
});
test('completed repair resolves a partial objective without rewriting its history',()=>{
  const state=executed();
  const repair=apply(state,assessment(state,{decision:'revise',coverage:[{objective_id:'analyze',status:'partial',refs:['observation-a'],explanation:'Conflict'}],
    follow_ups:[objective('repair',{resolves:['analyze']})]}));
  assert.deepEqual(repair.progress_events.map(item=>[item.step_id,item.phase]),[['analyze','settled'],['repair','started']]);
  assert.equal(repair.progress_events[0].outcome,'partial');
  const after=apply(repair.state,record(repair.state,{findings:[{id:'finding-b',text:'Corrected',status:'supported',refs:['observation-b']}]}),
    {receipts:[receipt(repair.state,{ref:'observation-b'})]}).state;
  const done=apply(after,assessment(after,{coverage:[{objective_id:'repair',status:'met',refs:['observation-b'],explanation:'Recomputed'}],
    checks:[{description:'Compare with source',status:'passed',refs:['observation-b'],explanation:'Compared correction'}]}));
  assert.equal(done.state.phase,'done');assert.equal(done.state.objectives[0].status,'partial');
  assert.deepEqual(done.progress_events.map(item=>item.step_id),['repair']);
  assert.equal(done.state.findings.length,2);
});
test('failed receipt is a diagnostic source, never successful coverage',()=>{
  const start=initialized();
  const state=apply(start,record(start,{outcome:'failed',findings:[],limitations:['Tool failed']}),{receipts:[receipt(start,{status:'failed'})]}).state;
  assert.throws(()=>apply(state,assessment(state)));
});
test('resolution cannot refer to unknown, unexecuted or cyclic objectives',()=>{
  assert.throws(()=>apply(null,plan([objective('a',{resolves:['a']})])));
  const state=executed();
  assert.throws(()=>apply(state,assessment(state,{decision:'revise',follow_ups:[objective('repair',{resolves:['missing']})]})));
  assert.throws(()=>apply(state,assessment(state,{decision:'revise',follow_ups:[objective('repair',{resolves:['analyze'],depends_on:['analyze']})]})));
});
test('file delivery accepts re-inspected owned products and does not trust unknown product refs',()=>{
  const first=apply(null,{...plan(),output_mode:'files'}).state;
  const product={ref:'product-v1',path:'report.html',action_id:first.pending_action.id,attempt_id:'attempt-a',status:'ready'};
  assert.throws(()=>apply(first,record(first,{product_refs:['product-v1']}),{receipts:[receipt(first)]}));
  const state=apply(first,record(first,{product_refs:['product-v1']}),{receipts:[receipt(first)],products:[product]}).state;
  assert.equal(apply(state,assessment(state),{products:[product]}).state.phase,'done');
});
test('repair replaces the active same-path version and preserves real earlier hash provenance',()=>{
  const directory=mkdtempSync(join(tmpdir(),'enterprise-cycle-'));
  try {
    const file=join(directory,'report.html');
    const inspect=state=>({ref:'workspace-product:report.html:'+createHash('sha256').update(readFileSync(file)).digest('hex'),
      path:'report.html',action_id:state.pending_action.id,attempt_id:'attempt-a',status:'ready'});
    const first=apply(null,{...plan(),output_mode:'files'}).state;
    writeFileSync(file,'<html>Initial estimate: 84</html>');const oldProduct=inspect(first);
    const recorded=apply(first,record(first,{product_refs:[oldProduct.ref]}),{receipts:[receipt(first)],products:[oldProduct]}).state;
    const repair=apply(recorded,assessment(recorded,{decision:'revise',coverage:[{objective_id:'analyze',status:'partial',refs:['observation-a'],explanation:'Actual source says 85'}],
      follow_ups:[objective('repair',{resolves:['analyze']})]})).state;
    writeFileSync(file,'<html>Corrected result: 85</html>');const currentProduct=inspect(repair);
    assert.notEqual(currentProduct.ref,oldProduct.ref);
    const after=apply(repair,record(repair,{findings:[{id:'corrected',text:'85',status:'supported',refs:['observation-b']}],product_refs:[currentProduct.ref]}),
      {receipts:[receipt(repair,{ref:'observation-b'})],products:[currentProduct]}).state;
    assert.deepEqual(after.product_refs,[currentProduct.ref]);
    assert.deepEqual(after.active_products,[{path:'report.html',ref:currentProduct.ref}]);
    assert.deepEqual(after.product_history.map(item=>item.ref),[oldProduct.ref,currentProduct.ref]);
    assert.equal(after.product_history[0].producer_action_id,first.pending_action.id);
    assert.ok(after.admitted_refs.includes(oldProduct.ref));
    const result=apply(after,assessment(after,{coverage:[{objective_id:'repair',status:'met',refs:['observation-b'],explanation:'Actual corrected output'}],
      checks:[{description:'Compare with source',status:'passed',refs:['observation-b'],explanation:'Rechecked actual source'}]}),{products:[currentProduct]});
    assert.equal(result.state.phase,'done');
  }finally {rmSync(directory,{recursive:true,force:true});}
});
test('delivery identifies only changed or unavailable products without altering accepted state',()=>{
 const first=apply(null,{...plan(),output_mode:'files'}).state;
 const products=['report.html','metrics.csv','daily.csv','work/metrics.json'].map(path=>({path,ref:'v1:'+path,
   action_id:first.pending_action.id,attempt_id:'attempt-a',status:'ready'}));
 const state=apply(first,record(first,{product_refs:products.map(item=>item.ref)}),{receipts:[receipt(first)],products}).state;
 const frozen=structuredClone(state),current=products.map(item=>item.path==='work/metrics.json'?{...item,ref:'v2:metrics'}:item);
 for(const available of [current,current.slice(0,3)]){
  assert.throws(()=>apply(state,assessment(state),{products:available}),error=>{
   assert.equal(error.code,'research_product_version_mismatch');
   assert.deepEqual(error.product_mismatches,{total:1,truncated:false,products:[{path:'work/metrics.json',registered_ref:'v1:work/metrics.json',
     current_ref:available.length===4?'v2:metrics':null,status:available.length===4?'changed':'unavailable'}]});return true;
  });
  assert.deepEqual(state,frozen);
 }
 assert.throws(()=>apply(state,assessment(state),{products:[...products.slice(0,3),{...products[3],ref:'x'.repeat(limits.snapshotBytes*2)}]}),error=>{
  assert.equal(error.code,'research_product_version_mismatch');assert.equal(error.product_mismatches.total,1);
  assert.equal(error.product_mismatches.truncated,true);
  assert.ok(Buffer.byteLength(JSON.stringify(error.product_mismatches))<=limits.snapshotBytes);return true;
 });
});
test('objective identities match the registered public record contract',()=>{
  for(const id of ['bad id','a/b','a'.repeat(129)])assert.throws(()=>apply(null,plan([objective(id)])));
});
test('published fields explain IDs, references, repair and exact check correspondence',()=>{
  const [p,r,a]=cycleToolParameters.oneOf.map(branch=>branch.properties);
  for(const field of ['id','depends_on','resolves','checks','input_refs'])assert.ok(p.objectives.items.properties[field].description);
  assert.match(p.objectives.items.properties.resolves.description,/plan.*\[\]/i);
  assert.match(p.source_refs.description,/host/i);assert.match(r.action_id.description,/pending_action/);
  assert.match(r.product_refs.description,/relative.*path/i);
  assert.match(a.checks.items.properties.description.description,/exact/i);
  assert.match(a.coverage.items.properties.objective_id.description,/pending_action/);
});
test('real model misreading of resolves is rejected before graph traversal with repair guidance',()=>{
  assert.throws(()=>apply(null,plan([objective('data-profile',{resolves:['数据结构与可用性']})])),
    error=>/data-profile/.test(error.message)&&/resolves/.test(error.message)&&/\[\]/.test(error.message)&&!/数据结构与可用性/.test(error.message));
  assert.throws(()=>apply(null,plan([objective('data-profile',{depends_on:null})])),/objectives\[0\]\.depends_on.*array/);
});
test('unknown dependency names its owner and field; forward references and empty arrays work',()=>{
  assert.throws(()=>apply(null,plan([objective('profile',{depends_on:['missing']})])),
    error=>/profile/.test(error.message)&&/depends_on/.test(error.message)&&/missing/.test(error.message)&&/objective.*id/i.test(error.message));
  assert.equal(apply(null,plan([objective('report',{depends_on:['profile']}),objective('profile')])).pending_action.objective_id,'profile');
  assert.equal(apply(null,plan([objective('profile')])).pending_action.objective_id,'profile');
});
test('missing passed check points to accepted check index without echoing task text',()=>{
  const state=executed();
  assert.throws(()=>apply(state,assessment(state,{checks:[{description:'Paraphrased check',status:'passed',refs:['observation-a'],explanation:'Actual comparison'}]})),
    error=>/analyze/.test(error.message)&&/checks\[0\]/.test(error.message)&&/exact/i.test(error.message)&&!/Compare with source/.test(error.message));
});
test('discovery creates sourced new research questions and replaces obsolete pending work',()=>{
  const first=apply(null,plan([objective('discover'),objective('old-report',{depends_on:['discover']})])).state;
  const discovery=apply(first,record(first,{findings:[{id:'discovery',text:'Observed a cross-source discrepancy',status:'supported',refs:['observation-a']}]}),{receipts:[receipt(first)]}).state;
  const result=apply(discovery,assessment(discovery,{decision:'continue',
    follow_ups:[objective('investigate',{derived_from:['discovery'],questions:['Why do the sources disagree?']})],
    supersedes:[{objective_id:'old-report',reason:'Report before resolving the observed discrepancy would be premature',replacement_ids:['investigate']}],
    reflection:{discoveries:['discovery'],unresolved_questions:[{question:'Why do the sources disagree?',derived_from:['discovery']}],next_step_reason:'Resolve the observed discrepancy first'}}));
  assert.equal(result.pending_action.objective_id,'investigate');
  assert.deepEqual(result.pending_action.questions,['Why do the sources disagree?']);
  assert.deepEqual(result.pending_action.derived_from,['discovery']);
  assert.equal(result.state.objectives.find(item=>item.id==='old-report').status,'superseded');
  assert.deepEqual(result.state.objectives.find(item=>item.id==='old-report').supersession.replacement_ids,['investigate']);
  assert.equal(result.progress_events.length,2);
  assert.equal(result.progress_events[0].text,'Analyze actual source');
  assert.equal(result.progress_events[0].result_summary,'Ready');
  assert.equal(result.progress_events[1].next_action_reason,'Resolve the observed discrepancy first');
  assert.ok(!result.progress_events.some(item=>item.step_id==='old-report'));
});
test('follow-up research takes priority over an earlier ready report without erasing old plan',()=>{
  const first=apply(null,plan([objective('discover'),objective('report')])).state;
  const discovery=apply(first,record(first),{receipts:[receipt(first)]}).state;
  const next=apply(discovery,assessment(discovery,{decision:'continue',follow_ups:[objective('new-question',{derived_from:['finding-a']})]}));
  assert.equal(next.pending_action.objective_id,'new-question');
  assert.equal(next.state.objectives.find(item=>item.id==='report').status,'pending');
});
test('sourced question results can produce further research and reach delivery through replacement coverage',()=>{
  const first=apply(null,plan([objective('discover'),objective('old',{depends_on:['discover']})])).state;
  const found=apply(first,record(first),{receipts:[receipt(first)]}).state;
  const investigation=apply(found,assessment(found,{decision:'continue',follow_ups:[objective('question-a',{derived_from:['finding-a']})],
    supersedes:[{objective_id:'old',reason:'Investigate before reporting',replacement_ids:['question-a']}]})).state;
  const studied=apply(investigation,record(investigation,{findings:[{id:'new-finding',text:'One assumption is refuted',status:'refuted',refs:['observation-b']}]}),
    {receipts:[receipt(investigation,{ref:'observation-b'})]}).state;
  const follow=apply(studied,assessment(studied,{decision:'revise',coverage:[{objective_id:'question-a',status:'partial',refs:['observation-b'],explanation:'A remaining contradiction'}],
    follow_ups:[objective('question-b',{derived_from:['new-finding'],resolves:['question-a']})],
    reflection:{contradictions:[{finding_ids:['finding-a','new-finding'],summary:'Assumption changed'}],next_step_reason:'Check the changed assumption'}})).state;
  assert.equal(follow.pending_action.objective_id,'question-b');
  const repaired=apply(follow,record(follow,{findings:[{id:'resolution',text:'Actual new result',status:'supported',refs:['observation-c']}]}),
    {receipts:[receipt(follow,{ref:'observation-c'})]}).state;
  const done=apply(repaired,assessment(repaired,{coverage:[{objective_id:'question-b',status:'met',refs:['observation-c'],explanation:'Resolved'}],
    checks:[{description:'Compare with source',status:'passed',refs:['observation-c'],explanation:'Actual recheck'}]}));
  assert.equal(done.state.phase,'done');assert.equal(done.state.objectives.find(item=>item.id==='old').status,'superseded');
  assert.equal(done.state.findings.length,3);
});
test('new question provenance and reflection cannot invent accepted findings',()=>{
  assert.throws(()=>apply(null,plan([objective('a',{derived_from:['not-found']})])));
  const state=executed();
  for(const extra of [
    {follow_ups:[objective('new',{derived_from:['not-found']})]},
    {reflection:{discoveries:['not-found']}},
    {reflection:{unresolved_questions:[{question:'What?',derived_from:['not-found']}]}},
    {reflection:{contradictions:[{finding_ids:['not-found'],summary:'Conflict'}]}}
  ])assert.throws(()=>apply(state,assessment(state,{decision:'continue',follow_ups:[objective('new')],...extra})));
});
test('supersession rejects unknown replacements, cycles and already executed targets',()=>{
  const first=apply(null,plan([objective('discover'),objective('old',{depends_on:['discover']})])).state;
  const state=apply(first,record(first),{receipts:[receipt(first)]}).state;
  for(const extra of [
    {supersedes:[{objective_id:'old',reason:'Change',replacement_ids:['missing']}]},
    {supersedes:[{objective_id:'discover',reason:'Change',replacement_ids:['new']}]},
    {supersedes:[{objective_id:'unknown',reason:'Change',replacement_ids:['new']}]},
    {follow_ups:[objective('new',{depends_on:['old']})],supersedes:[{objective_id:'old',reason:'Change',replacement_ids:['new']}]},
  ])assert.throws(()=>apply(state,assessment(state,{decision:'continue',follow_ups:[objective('new')],...extra})));
});
test('old checkpoint action metadata can be derived, but changed accepted metadata is rejected',()=>{
  const state=initialized();delete state.pending_action.questions;delete state.pending_action.derived_from;delete state.pending_priority;
  assert.equal(apply(state,record(state),{receipts:[receipt(state)]}).state.phase,'assessing');
  const changed=initialized();changed.pending_action.questions=['A different unauthorized objective'];
  assert.throws(()=>apply(changed,record(changed),{receipts:[receipt(changed)]}));
});
test('new question priority respects dependencies between new research objectives',()=>{
  const first=apply(null,plan([objective('discover'),objective('old-report')])).state;
  const state=apply(first,record(first),{receipts:[receipt(first)]}).state;
  const next=apply(state,assessment(state,{decision:'continue',follow_ups:[objective('synthesis',{depends_on:['branch-a']}),objective('branch-a')]}));
  assert.equal(next.pending_action.objective_id,'branch-a');
  assert.deepEqual(next.state.pending_priority,['synthesis']);
});
const adoptionState=()=>{
  const first=apply(null,plan([objective('discover'),objective('flow',{depends_on:['discover']})])).state;
  return apply(first,record(first),{receipts:[receipt(first)]}).state;
};
test('reflection discovery can be adopted by an existing pending objective before activation',()=>{
  const state=adoptionState(),original=structuredClone(state),question='Does the observed constraint coincide with the anomaly?';
  const next=apply(state,assessment(state,{decision:'continue',reflection:{unresolved_questions:[{question,derived_from:['finding-a']}]},
    question_adoptions:[{objective_id:'flow',questions:[question,question,'What changed?'],derived_from:['finding-a','finding-a']}]}));
  assert.equal(next.pending_action.objective_id,'flow');
  assert.deepEqual(next.pending_action.questions,['What changed?',question]);
  assert.deepEqual(next.pending_action.derived_from,['finding-a']);
  assert.deepEqual(next.state.question_adoptions,[{objective_id:'flow',questions:[question],derived_from:['finding-a'],
    assessment_action_id:state.pending_action.id,round:1}]);
  assert.deepEqual(next.progress_events.at(-1).questions,next.pending_action.questions);
  assert.deepEqual(state,original,'Successful adoption does not mutate caller checkpoint');
});
test('question adoption rejects unknown finding, nonpending objective and empty metadata without state mutation',()=>{
  const state=adoptionState(),original=structuredClone(state);
  for(const item of [
    {objective_id:'unknown',questions:['New?'],derived_from:['finding-a']},
    {objective_id:'discover',questions:['New?'],derived_from:['finding-a']},
    {objective_id:'flow',questions:['New?'],derived_from:['invented']},
    {objective_id:'flow',questions:[],derived_from:['finding-a']},
    {objective_id:'flow',questions:['New?'],derived_from:[]},
  ]){
    assert.throws(()=>apply(state,assessment(state,{decision:'continue',question_adoptions:[item]})));
    assert.deepEqual(state,original);
  }
});
test('adoption provenance requires a committed finding with successful source observations',()=>{
  const first=apply(null,plan([objective('discover'),objective('flow')])).state;
  const state=apply(first,record(first,{findings:[{id:'finding-a',text:'Observed',status:'supported',refs:['observation-a']},
    {id:'unsupported',text:'Unobserved hypothesis',status:'hypothesis',refs:[]}]}),{receipts:[receipt(first)]}).state;
  assert.throws(()=>apply(state,assessment(state,{decision:'continue',question_adoptions:[{objective_id:'flow',questions:['New?'],derived_from:['unsupported']}]})),/successful source/);
  const withoutSource=structuredClone(state);withoutSource.successful_refs=[];
  assert.throws(()=>apply(withoutSource,assessment(withoutSource,{decision:'continue',coverage:[{objective_id:'discover',status:'partial',refs:[],explanation:'Gap'}],checks:[],
    question_adoptions:[{objective_id:'flow',questions:['New?'],derived_from:['finding-a']}]})),/successful source/);
});
test('question adoption uses configured aggregate capacity and terminal decisions cannot adopt future work',()=>{
  const state=adoptionState(),original=structuredClone(state);
  const extra={question_adoptions:[{objective_id:'flow',questions:['New?'],derived_from:['finding-a']}]};
  assert.throws(()=>apply(state,assessment(state,{decision:'continue',...extra}),{},{...limits,maxQuestions:2}),error=>error.code==='research_capacity_exceeded');
  assert.deepEqual(state,original);
  assert.throws(()=>apply(state,assessment(state,{decision:'limited',...extra})),/continuing/);
});
test('adoption-only revision deduplicates repeated entries and leaves the old input contract compatible',()=>{
  const state=adoptionState();delete state.question_adoptions;
  const adoption={objective_id:'flow',questions:['A discovered question?'],derived_from:['finding-a']};
  const next=apply(state,assessment(state,{decision:'revise',question_adoptions:[adoption,structuredClone(adoption)]}));
  assert.deepEqual(next.pending_action.questions,['What changed?','A discovered question?']);
  assert.deepEqual(next.pending_action.derived_from,['finding-a']);
  assert.equal(next.state.question_adoptions.length,1);
  assert.equal(state.question_adoptions,undefined);
});
test('a superseded pending target cannot receive questions in the same assessment',()=>{
  const state=adoptionState(),before=structuredClone(state);
  assert.throws(()=>apply(state,assessment(state,{decision:'continue',follow_ups:[objective('replacement')],
    supersedes:[{objective_id:'flow',reason:'Change source method',replacement_ids:['replacement']}],
    question_adoptions:[{objective_id:'flow',questions:['New?'],derived_from:['finding-a']}]})),/pending objective/);
  assert.deepEqual(state,before);
});
test('conditional ready projection exposes independent siblings, excludes downstream work and does not mutate state',()=>{
  const first=apply(null,plan([objective('discover'),objective('a',{depends_on:['discover']}),objective('b',{depends_on:['discover']}),
    objective('report',{depends_on:['a','b']})])).state;
  const state=apply(first,record(first),{receipts:[receipt(first)]}).state,before=structuredClone(state);
  const ready=readyObjectivesAfterAssessment(state);
  assert.deepEqual(ready.map(item=>item.id),['a','b']);assert.deepEqual(ready[0].questions,['What changed?']);
  ready[0].questions.push('Projection caller mutation');assert.deepEqual(state,before);
  assert.equal(state.objectives[0].status,'executed');
});
test('conditional ready projection uses the same repair satisfaction as actual activation',()=>{
  const state=adoptionState();
  const repair=apply(state,assessment(state,{decision:'revise',coverage:[{objective_id:'discover',status:'partial',refs:['observation-a'],explanation:'Repair needed'}],
    follow_ups:[objective('repair',{resolves:['discover']})]})).state;
  const executedRepair=apply(repair,record(repair,{findings:[{id:'repair-finding',text:'Corrected',status:'supported',refs:['repair-observation']}]}),
    {receipts:[receipt(repair,{ref:'repair-observation'})]}).state;
  assert.deepEqual(readyObjectivesAfterAssessment(executedRepair).map(item=>item.id),['flow']);
});
test('conditional ready projection follows superseded requirements through their replacement',()=>{
  const first=apply(null,plan([objective('discover'),objective('old',{depends_on:['discover']}),objective('report',{depends_on:['old']})])).state;
  const state=apply(first,record(first),{receipts:[receipt(first)]}).state;
  const replacement=apply(state,assessment(state,{decision:'continue',follow_ups:[objective('replacement')],
    supersedes:[{objective_id:'old',reason:'Use discovered method',replacement_ids:['replacement']}]})).state;
  const next=apply(replacement,record(replacement,{findings:[{id:'replacement-finding',text:'Actual result',status:'supported',refs:['replacement-observation']}]}),
    {receipts:[receipt(replacement,{ref:'replacement-observation'})]}).state;
  assert.deepEqual(readyObjectivesAfterAssessment(next).map(item=>item.id),['report']);
});
test('conditional ready projection is absent outside valid successful-work assessment',()=>{
  assert.deepEqual(readyObjectivesAfterAssessment(null),[]);assert.deepEqual(readyObjectivesAfterAssessment(initialized()),[]);
  const first=initialized();const failed=apply(first,record(first,{outcome:'failed',findings:[],limitations:['No source']})).state;
  assert.deepEqual(readyObjectivesAfterAssessment(failed),[]);
  const state=executed();const done=apply(state,assessment(state)).state;
  assert.deepEqual(readyObjectivesAfterAssessment(done),[]);
});
