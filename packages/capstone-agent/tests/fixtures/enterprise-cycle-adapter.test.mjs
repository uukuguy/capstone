import test from 'node:test';
import assert from 'node:assert/strict';
import {createEnterpriseResearchController} from '../../src/capstone_agent/resources/enterprise-research-runtime.mjs';
import {completeDeliveryReview} from '../../src/capstone_agent/resources/delivery-review.mjs';
const objective={id:'total',purpose:'Calculate total',questions:['What is the total?'],depends_on:[],expected_outputs:['report'],checks:['sum'],mode:'execute',input_refs:[],resolves:[]};
function setup({deliveryReview=false}={}){
  let revision=0,state=null,tool;const events=[],requests=[];
  const config={researchTaskId:'native-task',researchAttemptId:'attempt',researchOwner:{thread_id:'thread',work_id:'work',research_id:'research',goal_revision:1},researchSources:['material:source'],
    researchRuntime:{deliveryReview:{enabled:deliveryReview},limits:{maxRounds:10,maxFindings:100,maxQuestions:100,snapshotBytes:1048576}}};
  let reject=false,unknown=false;const hashes=new Map();
  const ports={config,readResearch:async()=>({research_revision:revision,state}),
    commitResearch:async(id,request)=>{requests.push({id,request});if(reject){reject=false;return {details:{ok:false,result:{status:'rejected',code:'research_reference_not_admitted'}}};}
      if(unknown){unknown=false;return {details:{ok:false,result:{status:'not_confirmed'}}};}
      assert.equal(request.expected_revision,revision);revision++;
      const notes=new Map((state?.notes??[]).map(n=>[n.note_id,n]));for(const n of request.changes.notes)notes.set(n.note_id,n);
      const claims=new Map((state?.claims??[]).map(n=>[n.claim_id,n]));for(const n of request.changes.claims)claims.set(n.claim_id,n);
      state={...state,...request.changes,notes:[...notes.values()],claims:[...claims.values()]};
      return {details:{ok:true,result:{status:'committed',receipt:{research_revision:revision}}}};},
    inspectProducts:async({productRefs})=>({ready:true,products:productRefs.filter(path=>hashes.get(path)!==null).map(path=>({path,sha256:hashes.get(path)??'a'.repeat(64),bytes:10}))}),
    onProgress:event=>events.push(event)};
  let controller;
  const reload=()=>{controller=createEnterpriseResearchController(ports);controller.register({on(){},registerTool(t){tool=t;}});};
  reload();
  return {get controller(){return controller;},reload,call:(id,args)=>tool.execute(id,args),events,requests,get state(){return state;},setHash(path,sha){hashes.set(path,sha);},reject(){reject=true;},unknown(){unknown=true;}};
}
const plan={operation:'plan',goal:'Correct report',output_mode:'files',objectives:[objective],source_refs:['material:source']};
test('selected final scope and full review gaps recover without promoting intermediate files',async()=>{
  const h=setup({deliveryReview:true});await h.call('plan',plan);
  const token=await h.controller.beginTool({toolCallId:'write',toolName:'write'});h.controller.endTool(token,{details:{native_research_source:{source_ref:'native-observation:write'}}});
  await h.call('record',{operation:'record',action_id:h.controller.status.pending_action.id,outcome:'completed',findings:[],product_refs:['data/intermediate.csv','report.md','metrics.csv'],limitations:[]});
  const command={operation:'assess',action_id:h.controller.status.pending_action.id,coverage:[{objective_id:'total',status:'met',refs:['native-observation:write'],explanation:'Observed output'}],checks:[{description:'sum',status:'passed',refs:['native-observation:write'],explanation:'Observed output'}],decision:'deliver',summary:'Requested report and metrics',follow_ups:[],delivery_product_refs:['report.md','metrics.csv']};
  const unknown=await h.call('unknown-final',{...command,delivery_product_refs:['not-registered.html']});
  assert.equal(unknown.details.ok,false);assert.equal(unknown.details.error.code,'research_delivery_selection_invalid');
  assert.equal(unknown.details.error.product_mismatches.products[0].reason,'unrecorded');
  assert.equal(h.requests.length,2,'unknown final paths cannot commit or create products');
  const rejected=await h.call('missing-review',command);assert.equal(rejected.details.ok,false);
  assert.deepEqual(rejected.details.error.delivery_review.missing_products,['report.md','metrics.csv']);
  const recovery=await h.controller.readState();assert.equal(recovery.delivery_review.selection_status,'requested_not_committed');
  assert.deepEqual(recovery.delivery_review.required_products.map(item=>item.path),['report.md','metrics.csv']);
  const summary=await h.controller.readState({includeReviewDetails:false});
  assert.equal(summary.delivery_review.required_count,2);assert.equal(summary.delivery_review.missing_count,2);
  assert.ok(!Object.hasOwn(summary.delivery_review,'required_products'),'automatic model context carries counts, not full review history');
  for(const path of ['report.md','metrics.csv']){
    const review=completeDeliveryReview({products:[{path,sha256:'a'.repeat(64),bytes:10}],documents:[{path,kind:'product',text:'Saved bytes',scope:'full_text'}],not_checked:[]},[{source:{id:path},status:'completed',answer:JSON.stringify({summary:'Read saved file',findings:[],not_checked:[]})}]);
    const reviewToken=await h.controller.beginTool({toolCallId:path,toolName:'agent_delegate'});
    const jobs=[{questions:objective.questions,expected_outputs:['Verified discrepancies']}];
    await assert.rejects(h.controller.delegationContext(jobs,{toolCallId:path}),/review|assess/i);
    const binding=await h.controller.delegationContext(jobs,{toolCallId:path,reviewMode:'delivery'});assert.equal(binding.review_mode,'delivery');
    h.controller.endTool(reviewToken,{details:{native_research_source:{source_ref:'native-observation:'+path},delivery_review:review}});
  }
  const result=await h.call('deliver',command);assert.equal(result.details.ok,true,JSON.stringify(result));
  assert.equal(result.details.result.delivery_products.length,2);
  const saved=JSON.parse(h.state.notes.at(-1).text).snapshot;
  assert.equal(saved.active_products.length,3);assert.equal(saved.product_history.length,3);assert.equal(saved.delivery_products.length,2);
});
test('changed final bytes expose registered/current versions and the legal reassessment recovery route',async()=>{
  const h=setup({deliveryReview:true});await h.call('plan',plan);
  const token=await h.controller.beginTool({toolCallId:'write',toolName:'write'});h.controller.endTool(token,{details:{native_research_source:{source_ref:'native-observation:write'}}});
  const recorded=await h.call('record',{operation:'record',action_id:h.controller.status.pending_action.id,outcome:'completed',findings:[],product_refs:['report.md'],limitations:[]});
  h.reload();
  h.setHash('report.md','b'.repeat(64));
  const result=await h.call('deliver',{operation:'assess',action_id:recorded.details.result.pending_action.id,coverage:[{objective_id:'total',status:'met',refs:['native-observation:write'],explanation:'Output'}],checks:[{description:'sum',status:'passed',refs:['native-observation:write'],explanation:'Output'}],decision:'deliver',summary:'Report',follow_ups:[],delivery_product_refs:['report.md']});
  assert.equal(result.details.ok,false);assert.equal(result.details.error.code,'research_product_version_mismatch');
  const mismatch=result.details.error.product_mismatches.products[0];
  assert.equal(mismatch.reason,'changed_version');assert.equal(mismatch.registered_sha256,'a'.repeat(64));assert.equal(mismatch.current_sha256,'b'.repeat(64));
  assert.notEqual(mismatch.registered_ref,mismatch.current_ref);
  assert.match(result.content[0].text,/partial.*revise.*resolves/);assert.match(result.content[0].text,/Do not rewrite correct files/);
  assert.equal(h.requests.length,2);assert.equal(h.controller.status.phase,'assessing');
  h.setHash('report.md',null);
  const unavailable=await h.call('unavailable',{operation:'assess',action_id:recorded.details.result.pending_action.id,coverage:[],checks:[],decision:'limited',summary:'Current report unavailable',follow_ups:[],delivery_product_refs:['report.md']});
  assert.equal(unavailable.details.ok,false);const missing=unavailable.details.error.product_mismatches.products[0];
  assert.equal(missing.reason,'unavailable');assert.equal(missing.registered_sha256,'a'.repeat(64));assert.equal(missing.current_sha256,null);
  assert.equal(h.requests.length,2);
});
test('read-only recovery returns the same current action and a detached snapshot after a rejected ID',async()=>{
  const h=setup();const initial=await h.call('plan',plan);
  const rejected=await h.call('wrong-record',{operation:'record',action_id:'cycle-'+ 'a'.repeat(64),outcome:'completed',findings:[],product_refs:[],limitations:[]});
  assert.equal(rejected.details.ok,false);
  assert.equal(rejected.details.error.action_mismatch.expected_action_id,initial.details.result.pending_action.id);
  assert.equal(rejected.details.error.action_mismatch.submitted_action_id,'cycle-'+ 'a'.repeat(64));
  const recovery=await h.controller.readState();
  assert.deepEqual(recovery.pending_action,initial.details.result.pending_action);
  assert.deepEqual(recovery.pending_action.questions,objective.questions);
  recovery.pending_action.questions.length=0;
  assert.deepEqual((await h.controller.readState()).pending_action.questions,objective.questions);
  const unsafe='not-an-id private task text';
  const invalid=await h.call('unsafe-record',{operation:'record',action_id:unsafe,outcome:'completed',findings:[],product_refs:[],limitations:[]});
  assert.equal(invalid.details.error.action_mismatch.submitted_action_id,null);
  assert.ok(!JSON.stringify(invalid).includes(unsafe));
  assert.equal(h.requests.length,1,'recovery and rejected IDs cannot commit');
});
test('split tools publish operation-specific structural hints without weakening schemas',()=>{
  const tools=[];const config={researchTaskId:'task',researchAttemptId:'attempt',researchOwner:{thread_id:'thread',work_id:'work',research_id:'research',goal_revision:1},applicationPolicy:{allowed_tools:['agent_research_plan','agent_research_record','agent_research_assess']}};
  const controller=createEnterpriseResearchController({config,readResearch:async()=>({research_revision:0,state:null}),commitResearch:async()=>{},inspectProducts:async()=>({ready:true,products:[]})});
  controller.register({on(){},registerTool:tool=>tools.push(tool)});
  const planTool=tools.find(tool=>tool.name==='agent_research_plan'),assessTool=tools.find(tool=>tool.name==='agent_research_assess');
  assert.match(planTool.parameters.properties.objectives.items.properties.expected_outputs.description,/array/i);
  assert.match(assessTool.parameters.properties.summary.description,/top.level/i);
  assert.match(assessTool.description,/reflection/);
  assert.ok(assessTool.parameters.required.includes('summary'));
  assert.equal(assessTool.parameters.additionalProperties,false);
});
test('completed review is restored from the same protected checkpoint without a new child',async()=>{
  const h=setup({deliveryReview:true});await h.call('plan',plan);
  const packet={products:[{path:'report.md',sha256:'a'.repeat(64),bytes:10}],documents:[{path:'report.md',kind:'product',scope:'full_text',text:'Actual report'}],not_checked:[]};
  const review=completeDeliveryReview(packet,[{source:{id:'actual-child'},status:'completed',answer:JSON.stringify({summary:'Read saved report',findings:[],not_checked:[]})}]);
  const token=await h.controller.beginTool({toolCallId:'review',toolName:'agent_delegate'});
  const source='native-observation:review';h.controller.endTool(token,{details:{native_research_source:{source_ref:source},delivery_review:review}});
  assert.equal((await h.call('record',{operation:'record',action_id:h.controller.status.pending_action.id,outcome:'completed',findings:[],product_refs:['report.md'],limitations:[]})).details.ok,true);
  const action=h.controller.status.pending_action;h.reload();
  const result=await h.call('assess',{operation:'assess',action_id:action.id,coverage:[{objective_id:'total',status:'met',refs:[source],explanation:'Actual current review'}],checks:[{description:'sum',status:'passed',refs:[source],explanation:'Observed review, not semantic proof'}],decision:'deliver',summary:'Current saved report reviewed',follow_ups:[]});
  assert.equal(result.details.ok,true,JSON.stringify(result));
});

test('opt-in delivery needs an actual completed current review, not parent self-check',async()=>{
  const h=setup({deliveryReview:true});await h.call('plan',plan);
  const write=await h.controller.beginTool({toolCallId:'write',toolName:'write'});
  h.controller.endTool(write,{details:{native_research_source:{source_ref:'native-observation:write'}}});
  await h.call('record',{operation:'record',action_id:h.controller.status.pending_action.id,outcome:'completed',findings:[],product_refs:['report.md'],limitations:[]});
  const assessment={operation:'assess',action_id:h.controller.status.pending_action.id,coverage:[{objective_id:'total',status:'met',refs:['native-observation:write'],explanation:'Self check'}],checks:[{description:'sum',status:'passed',refs:['native-observation:write'],explanation:'Self check'}],decision:'deliver',summary:'Saved report',follow_ups:[]};
  const rejected=await h.call('assess-no-review',assessment);assert.equal(rejected.details.ok,false);assert.match(rejected.content[0].text,/review/i);
  const delegate=await h.controller.beginTool({toolCallId:'review',toolName:'agent_delegate'});
  const fake={schema:'capstone-delivery-review/1',products:[{path:'report.md',sha256:'a'.repeat(64),bytes:10}],findings:[]};
  h.controller.endTool(delegate,{details:{native_research_source:{source_ref:'native-observation:fake'},delivery_review:fake}});
  assert.equal((await h.call('assess-fake',assessment)).details.ok,false,'unbranded parent-shaped metadata is not host review');
  const actual=completeDeliveryReview({products:fake.products,documents:[{kind:'product',path:'report.md',text:'Actual saved report',scope:'full_text'}],not_checked:['visual inspection unavailable']},[{source:{id:'review-child'},status:'completed',answer:JSON.stringify({summary:'Read current saved text',findings:[],not_checked:[]})}]);
  const token=await h.controller.beginTool({toolCallId:'real-review',toolName:'agent_delegate'});
  h.controller.endTool(token,{details:{native_research_source:{source_ref:'native-observation:actual-review'},delivery_review:actual}});
  assert.equal((await h.call('assess-reviewed',assessment)).details.ok,true);
  assert.ok(h.state.notes.some(note=>JSON.parse(note.text).receipts.some(receipt=>receipt.review?.schema==='capstone-delivery-review/1')));
});

test('review-only supporting script can block delivery and retain final products through limited delivery',async()=>{
  const h=setup({deliveryReview:true});await h.call('plan',plan);
  const write=await h.controller.beginTool({toolCallId:'write',toolName:'write'});
  h.controller.endTool(write,{details:{native_research_source:{source_ref:'native-observation:write'}}});
  await h.call('record',{operation:'record',action_id:h.controller.status.pending_action.id,outcome:'completed',findings:[],product_refs:['report.md','metrics.csv'],limitations:[]});
  const review=completeDeliveryReview({products:['report.md','metrics.csv','process.py'].map(path=>({path,sha256:'a'.repeat(64),bytes:10})),documents:[{kind:'product',path:'report.md',text:'Saved output',scope:'full_text'},{kind:'product',path:'metrics.csv',text:'label,value\nincidents,2',scope:'full_text'},{kind:'product',path:'process.py',text:'Producing script',scope:'full_text'}],not_checked:[]},
    [{source:{id:'review-child'},status:'completed',answer:JSON.stringify({summary:'Producing script disagrees with saved data.',findings:[{severity:'blocking',path:'process.py',description:'Observed inconsistency in producing script.'}],not_checked:[]})}]);
  const token=await h.controller.beginTool({toolCallId:'review-after-record',toolName:'agent_delegate'});
  const source='native-observation:review-after-record';h.controller.endTool(token,{details:{native_research_source:{source_ref:source},delivery_review:review}});
  const assessment={operation:'assess',action_id:h.controller.status.pending_action.id,coverage:[{objective_id:'total',status:'met',refs:[source],explanation:'Review result'}],checks:[{description:'sum',status:'passed',refs:[source],explanation:'Observed review'}],decision:'deliver',summary:'Saved product',follow_ups:[]};
  const rejected=await h.call('deliver',assessment);assert.equal(rejected.details.ok,false);
  assert.match(rejected.content[0].text,/decision limited/);
  assert.match(rejected.content[0].text,/Do not repeat review or rebuild usable outputs/);
  assert.ok(rejected.details.error.delivery_review.blocking_findings.some(item=>item.path==='process.py'));
  const limited=await h.call('limited',{...assessment,coverage:[{objective_id:'total',status:'partial',refs:[source],explanation:'Current product has a known remaining discrepancy'}],checks:[{description:'sum',status:'failed',refs:[source],explanation:'Actual review discrepancy'}],decision:'limited',summary:'Usable saved output retained with an explicit discrepancy.'});
  assert.equal(limited.details.ok,true);assert.equal(limited.details.result.status,'limited');
  assert.equal(limited.details.result.product_refs.length,2,'review-only process.py is not promoted into final products');
});

test('delivery reinspects products retained across distinct research objectives',async()=>{
  const h=setup();
  await h.call('plan',plan);
  for(const [index,path] of ['profile.csv','metrics.csv','report.html'].entries()){
    const current=h.controller.status.pending_action;
    const token=await h.controller.beginTool({toolCallId:'work-'+index,toolName:'bash'});
    const ref='native-observation:work-'+index;
    h.controller.endTool(token,{details:{native_research_source:{source_ref:ref}}});
    const recorded=await h.call('record-'+index,{operation:'record',action_id:current.id,outcome:'completed',
      findings:[],product_refs:[path],limitations:[]});
    assert.equal(recorded.details.ok,true);
    const assessed=await h.call('assess-'+index,{operation:'assess',action_id:h.controller.status.pending_action.id,
      coverage:[{objective_id:current.objective_id,status:'met',refs:[ref],explanation:'Observed output'}],
      checks:[{description:'sum',status:'passed',refs:[ref],explanation:'Checked'}],
      decision:index===2?'deliver':'continue',summary:'Resolved current question',
      follow_ups:index===2?[]:[{...objective,id:'follow-'+index}]});
    assert.equal(assessed.details.ok,true,JSON.stringify(assessed));
  }
  assert.equal(h.controller.status.phase,'done');
});
test('child questions bind to the admitted parent action before any child starts',async()=>{
  const h=setup();await h.call('plan',plan);
  const job={id:'independent-check',title:'Check the source total',instruction:'Check original rows',
    questions:[objective.questions[0]],expected_outputs:['Observed total and missing rows']};
  await assert.rejects(h.controller.delegationContext([job],{toolCallId:'delegate'}),/accepted current/);
  const token=await h.controller.beginTool({toolCallId:'delegate',toolName:'agent_delegate'});
  const binding=await h.controller.delegationContext([job],{toolCallId:'delegate'});
  assert.equal(binding.parent_action_id,h.controller.status.pending_action.id);
  assert.equal(binding.parent_step_id,'total');assert.ok(binding.checkpoint.ref.startsWith('runtime.checkpoint.'));
  await assert.rejects(h.controller.delegationContext([{...job,questions:['Unplanned speculation']}],{toolCallId:'delegate'}),/pending_action.questions/);
  await assert.rejects(h.controller.delegationContext([{...job,expected_outputs:[]}],{toolCallId:'delegate'}),/expected_outputs/);
  h.controller.endTool(token,{isError:false,details:{native_research_source:{source_ref:'native-observation:children'}}});
  await assert.rejects(h.controller.delegationContext([job],{toolCallId:'delegate'}),/accepted current/);
});
test('host execution receipts are required and assessment is separate',async()=>{
  const h=setup();const p=await h.call('plan',plan);assert.equal(p.details.ok,true);const action=p.details.result.pending_action;
  const record={operation:'record',action_id:action.id,outcome:'completed',findings:[],product_refs:['report.md'],limitations:[]};
  assert.equal((await h.call('fake',record)).details.ok,false,'no model-invented successful work');
  const token=await h.controller.beginTool({toolCallId:'write',toolName:'write'});
  h.controller.endTool(token,{isError:false,details:{native_research_source:{source_ref:'native-observation:real'}}});
  const r=await h.call('record',record);assert.equal(r.details.ok,true);assert.equal(r.details.result.phase,'assessing');
  const a=r.details.result.pending_action;
  const result=await h.call('assess',{operation:'assess',action_id:a.id,coverage:[{objective_id:'total',status:'met',refs:['native-observation:real'],explanation:'checked'}],
    checks:[{description:'sum',status:'passed',refs:['native-observation:real'],explanation:'sum agrees'}],decision:'deliver',summary:'Saved report agrees',follow_ups:[]});
  assert.equal(result.details.result.status,'done');assert.equal(await h.controller.continuation(),null);
  assert.deepEqual(h.events.map(e=>e.progress.phase),['started','updated','settled']);
  assert.ok(h.events.every(e=>e.attempt_id==='attempt'&&e.checkpoint.revision>0));
});
test('enabled research tools cannot bypass a committed plan; plain chat stays untouched',async()=>{
  const h=setup();assert.equal(await h.controller.continuation(),null);
  await assert.rejects(h.controller.beginTool({toolCallId:'unplanned',toolName:'bash'}),/plan/i);
  assert.match(await h.controller.continuation(),/plan/i);
  await h.call('plan',plan);
  const token=await h.controller.beginTool({toolCallId:'write',toolName:'write'});
  h.controller.endTool(token,{details:{native_research_source:{source_ref:'native-observation:actual'}}});
  const action=h.controller.status.pending_action;
  const recorded=await h.call('record',{operation:'record',action_id:action.id,outcome:'completed',findings:[],product_refs:['report.md'],limitations:[]});
  assert.equal(recorded.details.result.phase,'assessing');
  const check=await h.controller.beginTool({toolCallId:'check',toolName:'read'});
  h.controller.endTool(check,{details:{native_research_source:{source_ref:'native-observation:check'}}});
});
test('unknown checkpoint retries exact identity; rejected write permits correction',async()=>{
  const h=setup();h.unknown();assert.equal((await h.call('initial',plan)).details.ok,false);
  const first=structuredClone(h.requests[0]);assert.equal((await h.call('retry',plan)).details.ok,true);
  assert.deepEqual(h.requests[1],first);
  const action=h.controller.status.pending_action;h.reject();
  const record={operation:'record',action_id:action.id,outcome:'failed',findings:[],product_refs:[],limitations:['Tool failed']};
  assert.equal((await h.call('rejected',record)).details.ok,false);
  assert.equal((await h.call('corrected',record)).details.ok,true);
  assert.notEqual(h.requests.at(-1).id,h.requests.at(-2).id);
});
