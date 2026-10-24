import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

async function tool(options) {
  return (await import('../src/capstone_agent/resources/delegation-tool.mjs')).createDelegationTool(options);
}
const tasks = Array.from({length: 5}, (_, n) => ({id: 'task-' + n, title: 'Read source ' + n, instruction: 'Check source ' + n}));
const answer = text => ({responseText: text, aborted: false, turns: 1, usage: []});
const binding=()=>({owner:{thread_id:'thread-a',work_id:'work-a',research_id:'research-a',goal_revision:1},
  attempt_id:'attempt-a',parent_action_id:'action-a',parent_step_id:'objective-a',checkpoint:{ref:'checkpoint-a',revision:3}});

test('dependency results reach only ready children and failed prerequisites preserve unrelated answers',async()=>{
  const starts=[];
  const delegate=await tool({concurrency:2,maxTasks:8,runChild:async(job,callbacks)=>{
    starts.push(job.id);
    if(job.id==='b'){
      assert.equal(callbacks.dependencyResults[0].answer,'source evidence');
      assert.ok(Object.isFrozen(callbacks.dependencyResults[0]));
    }
    return job.id==='c'?{responseText:'',failure:'check failed'}:answer(job.id==='a'?'source evidence':'integrated');
  }});
  const result=await delegate.execute('dag',{tasks:[
    {id:'a',title:'Source',instruction:'Read'},
    {id:'b',title:'Integrate',instruction:'Use source',depends_on:['a']},
    {id:'c',title:'Other source',instruction:'Read'},
    {id:'d',title:'Blocked',instruction:'Use failed source',depends_on:['c']},
  ]});
  assert.deepEqual(starts,['a','c','b']);
  assert.equal(result.details.children[3].error.code,'child_dependency_failed');
  assert.deepEqual(result.details.children[3].blocked_by,['c']);
  assert.equal(result.details.children[1].answer,'integrated');
});

test('review selection uses host packet and actual child result; failure cannot pass',async()=>{
  const packet={schema:'capstone-delivery-review-packet/1',products:[{path:'report.html',sha256:'a'.repeat(64),bytes:123}],documents:[{path:'report.html',kind:'product',scope:'text_projection',text:'Actual saved report'}],not_checked:['visual content not inspected']};
  const delegate=await tool({concurrency:1,maxTasks:5,admitTasks:()=>binding(),
    prepareReview:async(paths,{jobs})=>{assert.deepEqual(paths,['report.html']);assert.equal(jobs[0].id,tasks[0].id);return packet;},
    runChild:async(job,hooks)=>{assert.equal(hooks.reviewPacket.documents[0].text,'Actual saved report');
      return answer(JSON.stringify({summary:'Read supplied text',findings:[],not_checked:[]}));}});
  assert.ok(delegate.parameters.properties.review_products);
  const result=await delegate.execute('review',{tasks:tasks.slice(0,1),review_products:['report.html']});
  assert.equal(result.isError,false);assert.equal(result.details.delivery_review.schema,'capstone-delivery-review/1');
  assert.deepEqual(result.details.delivery_review.child_ids,[tasks[0].id]);
  assert.equal(result.details.delivery_review.coverage[0].supplied_chars,19);
  const failed=await tool({concurrency:1,maxTasks:5,prepareReview:async()=>packet,runChild:async()=>({...answer('partial'),failure:'Child failed'})});
  const unavailable=await failed.execute('fail',{tasks:tasks.slice(0,1),review_products:['report.html']});
  assert.equal(unavailable.isError,true);assert.equal(unavailable.details.delivery_review,undefined);
  const legacy=await tool({concurrency:1,maxTasks:5,runChild:async()=>answer('Ordinary task')});
  assert.equal(legacy.parameters.properties.review_products,undefined);
  assert.equal((await legacy.execute('old',{tasks:tasks.slice(0,1)})).isError,false);
});

test('delivery mode is issued only after preparation and cannot expose review child tools',async()=>{
  const order=[],events=[];const packet={products:[{path:'report.html',sha256:'a'.repeat(64),bytes:1}],documents:[{path:'report.html',kind:'product',text:'Actual bytes',scope:'full_text'}],not_checked:[]};
  const delegate=await tool({concurrency:1,maxTasks:5,emit:event=>events.push(event),
    prepareReview:async()=>{order.push('prepared');return packet;},
    admitTasks:(_jobs,context)=>{order.push('admitted');assert.equal(context.reviewMode,'delivery');return {...binding(),review_mode:'delivery'};},
    runChild:async()=>answer(JSON.stringify({summary:'Read actual bytes',findings:[],not_checked:[]}))});
  assert.equal((await delegate.execute('review',{tasks:tasks.slice(0,1),review_products:['report.html']})).isError,false);
  assert.deepEqual(order,['prepared','admitted']);assert.ok(events.every(event=>event.review_mode==='delivery'));
  let admitted=false;
  const bad=await tool({concurrency:1,maxTasks:5,prepareReview:async()=>{throw new Error('No actual packet');},admitTasks:()=>{admitted=true;return binding();},runChild:async()=>answer('unused')});
  await assert.rejects(bad.execute('failed',{tasks:tasks.slice(0,1),review_products:['report.html']}),/packet/);assert.equal(admitted,false);
  const noTools=await tool({concurrency:1,maxTasks:5,emit:event=>{assert.notEqual(event.type,'delegation_child_tool');},prepareReview:async()=>packet,
    runChild:async(_job,hooks)=>{hooks.onToolActivity({type:'start',toolName:'read',toolCallId:'forbidden'});return answer('unexpected');}});
  const failed=await noTools.execute('tools',{tasks:tasks.slice(0,1),review_products:['report.html']});assert.equal(failed.isError,true);assert.equal(failed.details.children[0].status,'failed');
});

test('bounded parallel pool executes independent tasks and preserves input identity/order', async () => {
  let active = 0;
  let maximum = 0;
  const events = [];
  const delegate = await tool({concurrency: 2, maxTasks: 20, emit: e => events.push(e),
    runChild: async job => {
      maximum = Math.max(maximum, ++active);
      await new Promise(resolve => setTimeout(resolve, 2));
      active--;
      return answer('Answer for ' + job.id);
    }});
  const result = await delegate.execute('call-1', {tasks});
  assert.equal(maximum, 2);
  assert.deepEqual(result.details.children.map(child => child.source.id), tasks.map(job => job.id));
  assert.ok(result.details.children.every(child => child.status === 'completed'));
  assert.equal(result.details.children[3].answer, 'Answer for task-3');
  assert.equal(result.isError, false);
  assert.equal(events.filter(e => e.type === 'delegation_child_started').length, 5);
  assert.ok(events.every(e => e.subordinate === true));
  assert.equal(events[0].title, tasks[0].title);
});

test('pre-abort does not allocate and active cancel reaches running children without starting queued jobs', async () => {
  const pre = new AbortController(); pre.abort();
  const noRun = await tool({concurrency: 2, maxTasks: 10, runChild: () => assert.fail('must not allocate')});
  assert.ok((await noRun.execute('pre', {tasks}, pre.signal)).details.children.every(c => c.status === 'cancelled'));
  const controller = new AbortController();
  const started = [];
  const delegate = await tool({concurrency: 2, maxTasks: 10, runChild: async (job, {signal}) => {
    started.push(job.id);
    await new Promise(resolve => signal.addEventListener('abort', resolve, {once: true}));
    return {...answer('partial ' + job.id), aborted: true};
  }});
  const running = delegate.execute('active', {tasks}, controller.signal);
  await new Promise(resolve => setImmediate(resolve)); controller.abort();
  const result = await running;
  assert.deepEqual(started, ['task-0', 'task-1']);
  assert.ok(result.details.children.every(c => c.status === 'cancelled'));
  assert.equal(result.details.children[0].answer, 'partial task-0');
  assert.equal(result.details.children[2].error.code, 'child_not_started');
});

test('one failed child preserves other actual answers and never exposes thrown raw messages', async () => {
  const delegate = await tool({concurrency: 2, maxTasks: 10, runChild: async job => {
    if (job.id === 'task-0') throw new Error('SECRET_EXCEPTION_MUST_NOT_ESCAPE');
    if (job.id === 'task-1') return {...answer('partial answer'), failure: 'Host-safe provider unavailable'};
    return answer('usable');
  }});
  const result = await delegate.execute('failure', {tasks});
  assert.equal(result.details.children[0].status, 'failed');
  assert.equal(result.details.children[0].error.type, 'Error');
  assert.equal(result.details.children[1].answer, 'partial answer');
  assert.equal(result.details.children[1].error.message, 'Host-safe provider unavailable');
  assert.equal(result.details.children[2].status, 'completed');
  assert.equal(result.isError, false);
  assert.doesNotMatch(JSON.stringify(result), /SECRET_EXCEPTION/);
});

test('usage comes from actual child observations; missing values are not fabricated zero', async () => {
  const delegate = await tool({concurrency: 2, maxTasks: 10, runChild: async (job, hooks) => {
    hooks.onToolActivity({type: 'start', toolName: 'read', toolCallId: job.id});
    const usage = {input: 4, output: 2, cacheRead: 0, cacheWrite: 1, cost: null};
    hooks.onAssistantUsage(usage);
    return {...answer('source'), usage: [usage]};
  }});
  const result = await delegate.execute('usage', {tasks: tasks.slice(0, 2)});
  assert.deepEqual(result.details.usage, {input: 8, output: 4, cacheRead: 0, cacheWrite: 2, totalTokens: null, cost: null});
  assert.equal(result.details.children[0].usage.length, 1, 'callback and result must not double count');
});

test('host limits and exact schema reject model-selected configuration before execution', async () => {
  const delegate = await tool({concurrency: 3, maxTasks: 128, runChild: () => assert.fail('invalid task must not run')});
  assert.equal(delegate.name, 'agent_delegate');
  assert.equal(delegate.parameters.additionalProperties, false);
  assert.equal(delegate.parameters.properties.tasks.maxItems, 128);
  assert.equal(delegate.parameters.properties.tasks.items.additionalProperties, false);
  for (const params of [{tasks: [tasks[0]], model: 'other'}, {tasks: [{...tasks[0], tools: ['bash']}]},
    {tasks: [tasks[0], tasks[0]]}, {tasks: []}]) {
    await assert.rejects(delegate.execute('invalid', params), /Invalid delegation/);
  }
  await assert.rejects(tool({runChild: () => {}, concurrency: 0, maxTasks: 5}), /positive/);
});

test('empty child output is an explicit failed outcome', async () => {
  const delegate = await tool({concurrency: 1, maxTasks: 10, runChild: async () => answer('')});
  const result = await delegate.execute('empty', {tasks: [tasks[0]]});
  assert.equal(result.details.children[0].status, 'failed');
  assert.equal(result.details.children[0].error.code, 'empty_child_output');
  assert.equal(result.isError, true);
});

test('missing observations from a failed child keep total usage unknown', async () => {
  const delegate = await tool({concurrency: 2, maxTasks: 10, runChild: async job => {
    if (job.id === 'task-0') throw new Error('transport failed before usage receipt');
    return {...answer('usable'), usage: [{input: 4, output: 2, cacheRead: 0, cacheWrite: 0, cost: 0}]};
  }});
  const result = await delegate.execute('unknown', {tasks: tasks.slice(0, 2)});
  assert.equal(result.details.usage.input, null);
  assert.equal(result.details.usage.cost, null);
});

test('host event failure waits for all running child cleanup before rejecting', async () => {
  let closed = false;
  const delegate = await tool({concurrency: 2, maxTasks: 10,
    emit: event => { if (event.type === 'delegation_child_finished' && event.child_id === 'task-0') throw new Error('receipt write failed'); },
    runChild: async job => {
      if (job.id === 'task-1') {
        await new Promise(resolve => setTimeout(resolve, 4));
        closed = true;
      }
      return answer('source');
    }});
  await assert.rejects(delegate.execute('receipt-failure', {tasks: tasks.slice(0, 2)}), /receipt write failed/);
  assert.equal(closed, true);
});

test('exact publication schema works with actual pinned SDK defineTool and argument validator', async () => {
  const root = resolve(import.meta.dirname, '../../../.grid-agent/runtime/pi/source/packages');
  const sdk = await import(pathToFileURL(resolve(root, 'coding-agent/dist/index.js')).href);
  const ai = await import(pathToFileURL(resolve(root, 'ai/dist/index.js')).href);
  const delegate = sdk.defineTool(await tool({concurrency: 2, maxTasks: 128, runChild: async () => answer('actual')}));
  const args = ai.validateToolArguments(delegate, {type: 'toolCall', id: 'schema', name: 'agent_delegate', arguments: {tasks: [tasks[0]]}});
  assert.deepEqual(args, {tasks: [tasks[0]]});
  const researchArgs={tasks:[{...tasks[0],questions:['Independent source question'],expected_outputs:['Actual finding']} ]};
  assert.deepEqual(ai.validateToolArguments(delegate,{type:'toolCall',id:'research-schema',name:'agent_delegate',arguments:researchArgs}),researchArgs);
  assert.throws(() => ai.validateToolArguments(delegate, {type: 'toolCall', id: 'bad-schema', name: 'agent_delegate',
    arguments: {tasks: [{...tasks[0], model: 'forbidden'}]}}));
});
test('host admits all branches once before actual overlapping work, with distinct questions and real results',async()=>{
  const jobs=tasks.slice(0,2).map((job,index)=>({...job,questions:['Question '+index],expected_outputs:['Output '+index]}));
  const events=[],seen=[];let admitted=0,active=0,maximum=0,release;
  const bothRunning=new Promise(resolve=>{release=resolve;});
  const hostBinding=binding();
  const delegate=await tool({concurrency:2,maxTasks:5,emit:event=>events.push(event),
    admitTasks:async(accepted,control)=>{
      admitted++;assert.equal(control.toolCallId,'branch-call');assert.equal(control.signal,undefined);
      assert.deepEqual(accepted,jobs);assert.equal(active,0);assert.ok(Object.isFrozen(accepted));
      assert.ok(Object.isFrozen(accepted[0].questions));return hostBinding;
    },
    runChild:async(job,hooks)=>{
      assert.equal(admitted,1);seen.push(job);maximum=Math.max(maximum,++active);
      assert.deepEqual(hooks.siblingTasks,jobs.filter(item=>item.id!==job.id).map(({id,title,questions,expected_outputs})=>({id,title,questions,expected_outputs})));
      assert.ok(Object.isFrozen(hooks.siblingTasks));
      if(active===2)release();await bothRunning;
      hooks.onToolActivity({type:'tool_execution_start',toolName:'read',toolCallId:job.id});
      active--;
      return job.id==='task-0'?answer('Actual independent result A'):{...answer('Actual incomplete result B'),failure:'Admitted source is missing'};
    }});
  const result=await delegate.execute('branch-call',{tasks:jobs});
  assert.equal(admitted,1);assert.equal(maximum,2);assert.deepEqual(seen,jobs);
  assert.equal(result.details.children[0].status,'completed');assert.equal(result.details.children[1].status,'failed');
  for(const event of events){
    const job=jobs.find(job=>job.id===event.child_id);
    assert.deepEqual(Object.fromEntries(Object.keys(hostBinding).map(key=>[key,event[key]])),hostBinding);assert.deepEqual(event.questions,job.questions);
    assert.deepEqual(event.expected_outputs,job.expected_outputs);assert.equal(event.subordinate,true);
  }
  assert.equal(events.filter(event=>event.type==='delegation_child_tool').length,2);
  const finishes=events.filter(event=>event.type==='delegation_child_finished');
  assert.deepEqual(finishes.map(event=>event.result_summary).sort(),['Actual incomplete result B','Actual independent result A'].sort());
  hostBinding.checkpoint.revision=900;
  assert.equal(events[0].checkpoint.revision,3,'Published binding cannot change after admission');
});
test('rejected or malformed host admission starts no child and emits no claimed work',async()=>{
  for(const admitTasks of [async()=>{throw new Error('HOST_ADMISSION_REJECTED');},async()=>undefined,
    async()=>({...binding(),private_token:'MUST_NOT_PUBLISH'}),async()=>({...binding(),checkpoint:{ref:'checkpoint-a',revision:-1}})]){
    const events=[];const delegate=await tool({concurrency:2,maxTasks:5,emit:event=>events.push(event),admitTasks,
      runChild:()=>assert.fail('Rejected branches must not run')});
    await assert.rejects(delegate.execute('rejected',{tasks:tasks.slice(0,2)}));assert.deepEqual(events,[]);
  }
});
test('generic branch metadata is optional but cannot inject host bindings or malformed arrays',async()=>{
  const seen=[];const delegate=await tool({concurrency:1,maxTasks:5,runChild:async job=>{seen.push(job);return answer('actual');}});
  await delegate.execute('generic',{tasks:[tasks[0],{...tasks[1],questions:['Distinct?'],expected_outputs:['Saved outcome']}]});
  assert.deepEqual(seen,[tasks[0],{...tasks[1],questions:['Distinct?'],expected_outputs:['Saved outcome']}]);
  for(const extra of [{binding:binding()},{questions:null},{questions:['']},{expected_outputs:'report.md'}])
    await assert.rejects(delegate.execute('invalid',{tasks:[{...tasks[0],...extra}]}),/Invalid delegation/);
});
test('thrown child has empty actual summary and safe failure outcome, never fabricated child text',async()=>{
  const events=[];const delegate=await tool({concurrency:1,maxTasks:5,admitTasks:async()=>binding(),emit:event=>events.push(event),
    runChild:async()=>{throw new Error('PRIVATE_THROWN_TEXT');}});
  await delegate.execute('failure',{tasks:[tasks[0]]});
  const end=events.find(event=>event.type==='delegation_child_finished');
  assert.equal(end.status,'failed');assert.equal(end.result_summary,'');assert.doesNotMatch(JSON.stringify(events),/PRIVATE_THROWN_TEXT/);
});
test('cancellation while admission waits cannot start a queued child',async()=>{
  const controller=new AbortController();let release,admitted=0;
  const admission=new Promise(resolve=>{release=resolve;});
  const delegate=await tool({concurrency:2,maxTasks:5,admitTasks:async(jobs,{signal})=>{
    admitted++;assert.equal(signal,controller.signal);await admission;return binding();},
    runChild:()=>assert.fail('Cancelled admitted batch must not start')});
  const running=delegate.execute('cancel-admission',{tasks:tasks.slice(0,2)},controller.signal);
  controller.abort();release();const result=await running;
  assert.equal(admitted,1);assert.ok(result.details.children.every(child=>child.status==='cancelled'));
});

test('failed review exposes safe finish diagnostics and exact packet feedback without accepting it',async()=>{
  const packet={fingerprint:'b'.repeat(64),products:[{path:'report.txt',sha256:'a'.repeat(64),bytes:4}],documents:[{path:'report.txt',kind:'product',text:'text'}],not_checked:[],source_selection:{source_excerpt_chars:16384,excluded:[]}};
  const delegate=await tool({concurrency:1,maxTasks:1,prepareReview:async(_paths,{source_refs})=>{assert.deepEqual(source_refs,['source:prior']);return packet;},runChild:async()=>({responseText:'',failure:'Model reached output limit.',failure_code:'model_output_limit',turns:1,modelResponses:1,usage:[{input:137885,output:65536}],finish:{stop_reason:'length',visible_text_chars:0,model_output_capacity:65536,effective_output_limit:null,reasoning_tokens:65536,secret:'DO_NOT_PUBLISH'}})});
  const result=await delegate.execute('review-limit',{tasks:[tasks[0]],review_products:['report.txt'],review_source_refs:['source:prior']});
  assert.equal(result.isError,true);assert.equal(result.details.children[0].error.code,'model_output_limit');
  assert.equal(result.details.children[0].finish.stop_reason,'length');assert.equal(result.details.children[0].usage[0].output,65536);
  assert.equal(result.details.review_packet.fingerprint,packet.fingerprint);assert.match(result.details.review_error.message,/unchanged packet/);
  assert.ok(!result.details.delivery_review);assert.doesNotMatch(JSON.stringify(result),/DO_NOT_PUBLISH/);
});
