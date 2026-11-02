// Real pinned SDK sessions, guarded delegation, current files and protected CAS.
// Only model responses are scripted; no Provider or network call is made.
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm,realpath} from 'node:fs/promises';
import {readFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {createEnterpriseResearchController} from '../src/capstone_agent/resources/enterprise-research-runtime.mjs';
import {createDeliveryReviewSession,applicationToolOptions} from '../src/capstone_agent/resources/general-sdk.mjs';
import {createManagedSubagents} from '../src/capstone_agent/resources/managed-subagents.mjs';
import {createDelegationTool} from '../src/capstone_agent/resources/delegation-tool.mjs';
import {prepareDeliveryReview,reviewChildPrompt} from '../src/capstone_agent/resources/delivery-review.mjs';
import {inspectResearchProducts} from '../src/capstone_agent/resources/research-products.mjs';

test('actual SDK reviews saved bytes, repair invalidates old receipt, parent records then delivers current version',async()=>{
  const sdkRoot=resolve(import.meta.dirname,'../../../.grid-agent/runtime/pi/source/packages');
  const sdk=await import(pathToFileURL(resolve(sdkRoot,'coding-agent/dist/index.js')).href);
  const ai=await import(pathToFileURL(resolve(sdkRoot,'ai/dist/index.js')).href);
  const root=await realpath(await mkdtemp(resolve(tmpdir(),'delivery-review-sdk-')));
  const oldCwd=process.cwd(),oldAgent=process.env.PI_CODING_AGENT_DIR;
  let count=0,closes=0,revision=0,state=null;const observedPolicies=[],branchEvents=[];
  const researchPolicy=readFileSync(resolve(import.meta.dirname,'../../enterprise-research-domain-pack/src/enterprise_research/resources/split-control/system-policy.md'),'utf8');
  const reviewPolicy=readFileSync(resolve(import.meta.dirname,'../../enterprise-research-domain-pack/src/enterprise_research/resources/delivery-review.md'),'utf8');
  try{
    process.chdir(root);process.env.PI_CODING_AGENT_DIR=resolve(root,'.agent');await mkdir(process.env.PI_CODING_AGENT_DIR);
    await writeFile('report.md','Total: 0\n');await writeFile('metrics.csv','total\n2\n');await writeFile('process.py','# saved supporting calculation script\n');await writeFile('intermediate.csv','value\n2\n');
    const reviewSources=[];
    for(const [file_name,origin,text] of [['README.md','original_input','SOURCE_DEFINITIONS_SENTINEL'.repeat(200)],['original.csv','original_input','x'.repeat(80000)],['old.py','previous_product','EXCLUDED_PRIOR_SCRIPT_BODY']]){
      await writeFile(file_name,text);reviewSources.push({path:resolve(root,file_name),file_name,origin,source_ref:'source:'+file_name,size_bytes:Buffer.byteLength(text),sha256:createHash('sha256').update(text).digest('hex')});
    }
    const model={id:'fixed',name:'Offline',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
    const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline'}}),isUsingOAuth:()=>false,
      streamSimple(_model,context){
        observedPolicies.push(context.systemPrompt);
        assert.deepEqual(context.tools,[],'no shell, write, or research mutation tools in review');
        assert.equal(context.messages.length,1,'review does not inherit parent history');
        const prompt=context.messages[0].content.filter(p=>p.type==='text').map(p=>p.text).join('\n');
        assert.match(prompt,/SOURCE_DEFINITIONS_SENTINEL/);assert.doesNotMatch(prompt,/EXCLUDED_PRIOR_SCRIPT_BODY/);
        const packet=JSON.parse(prompt.slice(prompt.indexOf('{"schema":"capstone-delivery-review-packet/1"')));
        assert.equal(packet.documents.find(x=>x.path==='original.csv').text.length,16384);
        assert.equal(packet.documents.find(x=>x.path==='original.csv').scope,'excerpt');
        assert.match(prompt,/total\\n2/);assert.match(prompt,/actual saved product text/);
        assert.doesNotMatch(context.systemPrompt,/PARENT_HISTORY_SENTINEL/);
        const incorrect=prompt.includes('Total: 0');
        const response={summary:'Compared supplied actual report text with supplied CSV.',findings:incorrect?[{severity:'blocking',path:'report.md',description:'Saved report total 0 contradicts saved CSV total 2.'}]:[],not_checked:['No visual inspection.']};
        count++;const message={role:'assistant',content:[{type:'text',text:JSON.stringify(response)}],api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),stopReason:'stop',usage:{input:20,output:10,cacheRead:0,cacheWrite:0,totalTokens:30,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}};
        const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:'stop',message});stream.end();return stream;
      }};
    const config={model:model.id,settings:{packages:[],extensions:[],skills:[]},extensions:[],allowedSkills:[],contextFiles:[{path:'parent-history',content:'PARENT_HISTORY_SENTINEL'}],
      applicationPolicy:{allowed_tools:['agent_delegate','agent_research_cycle','write']},systemPrompt:'PARENT_SYSTEM_SENTINEL: execute research work.',
      appendSystemPrompt:['PARENT_APPEND_SENTINEL\n'+researchPolicy,reviewPolicy],researchChannelPath:'protected-test-port',
      researchTaskId:'task-review',researchAttemptId:'attempt-review',researchOwner:{thread_id:'thread',work_id:'work',research_id:'research',goal_revision:1},researchSources:['material:source'],researchRuntime:{deliveryReview:{enabled:true}}};
    let control;const controller=createEnterpriseResearchController({config,
      readResearch:async()=>({research_revision:revision,state}),
      commitResearch:async(_id,request)=>{assert.equal(request.expected_revision,revision++);state={...state,...request.changes,notes:[...(state?.notes??[]),...request.changes.notes]};return {details:{ok:true,result:{status:'committed',receipt:{research_revision:revision}}}};},
      inspectProducts:async({productRefs})=>inspectResearchProducts(root,productRefs.map(path=>({path,role:'primary'})))});
    controller.register({on(){},registerTool(value){control=value;}});
    const objective={id:'report',purpose:'Deliver consistent report',questions:['Does the report agree with saved data?'],depends_on:[],expected_outputs:['report.md','metrics.csv'],checks:['agreement'],mode:'execute',input_refs:[],resolves:[]};
    assert.equal((await control.execute('plan',{operation:'plan',goal:'Consistent report',output_mode:'files',objectives:[objective],source_refs:['material:source']})).details.ok,true);
    const runner=createManagedSubagents({createChildSession:async({signal})=>{
      const owned=await createDeliveryReviewSession(config,sdk,runtime,{signal,cwd:root});return {session:owned.session,close:async()=>{await owned.close();closes++;}};
    }});
    const delegate=createDelegationTool({concurrency:1,maxTasks:5,emit:event=>branchEvents.push(event),admitTasks:(jobs,ctx)=>controller.delegationContext(jobs,ctx),
      prepareReview:(paths,{signal})=>prepareDeliveryReview(root,paths,{limits:{input_text_chars:100000},signal,sources:reviewSources}),
      runChild:(job,callbacks)=>runner.run({...callbacks,prompt:reviewChildPrompt(job,callbacks.reviewPacket)})});
    const guarded=applicationToolOptions(config,[delegate],()=>controller).customTools[0];
    const params={tasks:[{id:'independent-reader',title:'Review actual saved output',instruction:'Compare delivered prose with saved table, without assuming success.',questions:objective.questions,expected_outputs:['Discrepancies and uninspected scope']}],review_products:['report.md','metrics.csv','process.py']};
    const first=await guarded.execute('first-review',params);assert.equal(first.details.delivery_review.findings.length,1);
    assert.doesNotMatch(observedPolicies[0],/PARENT_SYSTEM_SENTINEL|PARENT_APPEND_SENTINEL|agent_research_plan|agent_research_record|agent_research_assess|native bash|pipefail/i,
      'the actual review model must not receive parent research flow or shell guidance');
    assert.match(observedPolicies[0],/untrusted/i);assert.match(observedPolicies[0],/Authority/);assert.match(observedPolicies[0],/network/i);
    await writeFile('report.md','Total: 2\n');
    const second=await guarded.execute('second-review',params);assert.equal(second.details.delivery_review.findings.length,0);
    assert.equal(second.details.children[0].model_responses,1);assert.equal(second.details.children[0].usage[0].input,20);
    assert.notEqual(first.details.delivery_review.products[0].sha256,second.details.delivery_review.products[0].sha256);
    const source=second.details.native_research_source.source_ref;
    const recorded=await control.execute('record',{operation:'record',action_id:controller.status.pending_action.id,outcome:'completed',findings:[{id:'checked-current-report',text:'Current saved report agrees with supplied table within text review.',status:'supported',refs:[source]}],product_refs:['intermediate.csv','report.md','metrics.csv'],limitations:['No visual inspection.']});
    assert.equal(recorded.details.ok,true);
    await assert.rejects(guarded.execute('ordinary-assess-child',{tasks:params.tasks}),/Assessment|review/);
    const afterRecord=await guarded.execute('after-record-review',params);assert.equal(afterRecord.isError,false);
    const branch=branchEvents.filter(event=>event.parent_tool_call_id==='after-record-review');
    assert.deepEqual(branch.map(event=>event.type),['delegation_child_started','delegation_child_response','delegation_child_finished']);
    assert.equal(branch[1].response_number,1);
    assert.ok(Number.isSafeInteger(branch[1].response_ms)&&branch[1].response_ms>=0);
    assert.ok(branch.every(event=>event.review_mode==='delivery'&&event.parent_action_id===recorded.details.result.pending_action.id));
    const result=await control.execute('assess',{operation:'assess',action_id:controller.status.pending_action.id,coverage:[{objective_id:'report',status:'met',refs:[source],explanation:'Current text review observation'}],checks:[{description:'agreement',status:'passed',refs:[source],explanation:'Independent child read current supplied content; no semantic certification.'}],decision:'deliver',summary:'Current saved text was independently reviewed.',follow_ups:[],delivery_product_refs:['report.md','metrics.csv']});
    assert.equal(result.details.ok,true,JSON.stringify(result));assert.equal(controller.status.phase,'done');assert.equal(count,3);assert.equal(closes,3);
    assert.ok(state.notes.some(note=>JSON.parse(note.text).receipts.some(receipt=>receipt.review?.coverage?.some(doc=>doc.path==='report.md'))));
    const final=JSON.parse(state.notes.at(-1).text).snapshot;
    assert.deepEqual(final.active_products.map(item=>item.path),['intermediate.csv','report.md','metrics.csv'],'recorded intermediates remain process products');
    assert.deepEqual(final.delivery_products.map(item=>item.path),['report.md','metrics.csv'],'only explicit final scope is required; review-only script is not promoted');
  }finally{process.chdir(oldCwd);if(oldAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=oldAgent;await rm(root,{recursive:true,force:true});}
});

test('actual SDK output-limit stop retains observed finish and usage without reasoning content',async()=>{
  const sdkRoot=resolve(import.meta.dirname,'../../../.grid-agent/runtime/pi/source/packages');
  const sdk=await import(pathToFileURL(resolve(sdkRoot,'coding-agent/dist/index.js')).href);
  const ai=await import(pathToFileURL(resolve(sdkRoot,'ai/dist/index.js')).href);
  const root=await realpath(await mkdtemp(resolve(tmpdir(),'review-finish-sdk-'))),before=process.cwd(),beforeAgent=process.env.PI_CODING_AGENT_DIR;
  try{
    process.chdir(root);process.env.PI_CODING_AGENT_DIR=resolve(root,'.agent');await mkdir(process.env.PI_CODING_AGENT_DIR);
    const model={id:'fixed',name:'Offline',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
    const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline'}}),isUsingOAuth:()=>false,streamSimple(){
      const message={role:'assistant',content:[],api:model.api,provider:model.provider,model:model.id,timestamp:0,stopReason:'length',usage:{input:70,output:1024,reasoning:1024,cacheRead:0,cacheWrite:0,totalTokens:1094,cost:{total:0}}};
      const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:'length',message});stream.end();return stream;
    }};
    const config={model:'fixed',settings:{packages:[],extensions:[],skills:[]},extensions:[],allowedSkills:[],contextFiles:[],applicationPolicy:{allowed_tools:['agent_delegate']}};
    const runner=createManagedSubagents({createChildSession:({signal})=>createDeliveryReviewSession(config,sdk,runtime,{signal,cwd:root})});
    const result=await runner.run({prompt:'Review supplied text. Return only structured findings.'});
    assert.equal(result.finish.stop_reason,'length');assert.equal(result.finish.visible_text_chars,0);
    assert.equal(result.finish.reasoning_tokens,1024);assert.equal(result.finish.model_output_capacity,1024);
    assert.equal(result.finish.effective_output_limit,null);assert.equal(result.usage[0].output,1024);
    assert.equal(result.modelResponses,1);assert.match(result.failure,/output token limit/);
  }finally{process.chdir(before);if(beforeAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=beforeAgent;await rm(root,{recursive:true,force:true});}
});
