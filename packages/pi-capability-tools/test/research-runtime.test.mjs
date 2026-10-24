import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, writeFile, readFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {ResearchRuntime, serializeSnapshot, restoreSnapshot, UpstreamResearchStateMachine,
  UpstreamProfileResolver} from '../src/research-runtime/index.mjs';

const plan = {runId:'run-1', goal:'Deliver a source-consistent report', questions:['What does the source show?'], sourceRefs:['source:csv']};
const finding = (id, text) => ({id, text, status:'supported', refs:['receipt:'+id]});
const assessment = (decision, followUpQuestions=[]) => ({decision, summary:'Checked actual saved output', refs:['receipt:check'], followUpQuestions});
const ports = (overrides={}) => ({
  executeRound: async () => ({findings:[finding('a','Observed source')], observations:['receipt:a'], limitations:[], productRefs:['product:report']}),
  recordResult: async () => ({checkpointRef:'checkpoint:1', revision:1}),
  inspectProducts: async () => ({ready:true, actualProductRefs:['product:report'], limitations:[]}),
  ...overrides,
});

async function reachQuestion(runtime, state) {
  state=(await runtime.advance(state)).snapshot;
  assert.equal(state.phase,'extracting');
  state=(await runtime.advance(state)).snapshot;
  assert.equal(state.phase,'questioning');
  return state;
}

test('actual local CSV -> report -> observed discrepancy -> revised same report; no hidden model/network', async () => {
  const dir=await mkdtemp(join(tmpdir(),'research-core-'));
  const csv=join(dir,'input.csv'), report=join(dir,'report.md');
  await writeFile(csv,'item,value\na,3\nb,7\n');
  let executions=0, evaluations=0; const records=[];
  const oldFetch=globalThis.fetch;
  globalThis.fetch=()=>{throw new Error('Network must not run');};
  try {
    const runtime=new ResearchRuntime(ports({
      executeRound:async ({round}, control)=>{
        control.signal.throwIfAborted(); executions++;
        const source=await readFile(csv,'utf8');
        const sum=source.trim().split('\n').slice(1).reduce((n,row)=>n+Number(row.split(',')[1]),0);
        await writeFile(report,`Total: ${round===1?sum-1:sum}\n`);
        const actual=await readFile(report,'utf8');
        return {findings:[finding('sum',actual.trim())], observations:[`receipt:round-${round}`],
          limitations:actual===`Total: ${sum}\n`?[]:['Saved report total conflicts with source'], productRefs:['product:report']};
      },
      assess:async ({suppliedAssessment})=>{evaluations++; return suppliedAssessment;},
      recordResult:async value=>{records.push(value);return {checkpointRef:'checkpoint:'+records.length,revision:records.length};},
      inspectProducts:async()=>({ready:(await readFile(report,'utf8'))==='Total: 10\n', actualProductRefs:['product:report'],limitations:[]}),
    }));
    let state=await reachQuestion(runtime,runtime.init(plan));
    assert.equal(await readFile(report,'utf8'),'Total: 9\n');
    assert.equal(state.findings[0].text,'Total: 9');
    state=(await runtime.advance(state,{assessment:assessment('revise',['Correct the report total and check it'])})).snapshot;
    assert.equal(state.phase,'searching');
    state=restoreSnapshot(serializeSnapshot(state));
    state=await reachQuestion(runtime,state);
    state=(await runtime.advance(state,{assessment:assessment('deliver')})).snapshot;
    assert.equal(state.phase,'drafting');
    state=(await runtime.advance(state)).snapshot;
    const done=await runtime.advance(state);
    assert.equal(done.status,'done');
    assert.equal(await readFile(report,'utf8'),'Total: 10\n');
    assert.equal(done.snapshot.findings[0].text,'Total: 10');
    assert.deepEqual(done.snapshot.actualProductRefs,['product:report']);
    assert.equal(executions,2); assert.equal(evaluations,2);
    assert.deepEqual(records.map(x=>x.kind),['round','assessment','round','assessment']);
    assert.equal(new Set(records.map(x=>x.recordId)).size,4);
  } finally {globalThis.fetch=oldFetch; await rm(dir,{recursive:true,force:true});}
});

test('missing supplied assessment does not invoke evaluator or repeat work',async()=>{
  let count=0;
  const runtime=new ResearchRuntime(ports({assess:async()=>{count++;throw new Error('Unexpected model call');}}));
  const state=await reachQuestion(runtime,runtime.init(plan));
  const wait=await runtime.advance(state);
  assert.equal(wait.status,'needs_assessment');assert.equal(count,0);
  assert.deepEqual(wait.snapshot,state);
});

test('cancellation interrupts a pending adapter and preserves input snapshot',async()=>{
  const controller=new AbortController(); let entered;
  const ready=new Promise(resolve=>entered=resolve);
  const runtime=new ResearchRuntime(ports({executeRound:async(_input,{signal})=>{
    entered(); await new Promise((_,reject)=>signal.addEventListener('abort',()=>reject(signal.reason),{once:true}));
  }}));
  const state=runtime.init(plan);const pending=runtime.advance(state,{signal:controller.signal});
  await ready;controller.abort();await assert.rejects(pending,{name:'AbortError'});
  assert.equal(state.round,0);assert.equal(state.phase,'searching');
});

test('record retry uses same completed result and identity, never executes again',async()=>{
  let calls=0,writes=0;const ids=[];
  const runtime=new ResearchRuntime(ports({executeRound:async()=>{calls++;return {findings:[],observations:[],limitations:[],productRefs:[]};},
    recordResult:async({recordId})=>{ids.push(recordId);if(++writes===1)throw new Error('uncertain commit');return {checkpointRef:'saved',revision:1};}}));
  let state=(await runtime.advance(runtime.init(plan))).snapshot;
  const retry=await runtime.advance(state);assert.equal(retry.status,'record_pending');
  state=restoreSnapshot(serializeSnapshot(retry.snapshot));
  assert.equal((await runtime.advance(state)).snapshot.phase,'questioning');
  assert.equal(calls,1);assert.deepEqual(ids,['run-1:1:round','run-1:1:round']);
});

test('round budget yields limited outcome, not false completion; custom override works',async()=>{
  const runtime=new ResearchRuntime(ports(),{maxRounds:1});
  const state=await reachQuestion(runtime,runtime.init(plan));
  const limited=await runtime.advance(state,{assessment:assessment('continue',['Need another source'])});
  assert.equal(limited.status,'limited');assert.equal(limited.reason,'round_limit');
  assert.notEqual(limited.snapshot.phase,'done');
  const expanded=new ResearchRuntime(ports(),{maxRounds:2});
  assert.equal((await expanded.advance(state,{assessment:assessment('continue',['Need another source'])})).snapshot.phase,'searching');
});

test('application-injected debug round budget interrupts before assessment persistence instead of limited recovery',async()=>{
  const records=[];
  const runtime=new ResearchRuntime(ports({recordResult:async value=>{records.push(value);return {checkpointRef:'saved',revision:records.length};}}),
    {runtimeLimits:{research_round_count:1},runtimeLimitMode:'debug'});
  const state=await reachQuestion(runtime,runtime.init(plan)), before=records.length;
  await assert.rejects(runtime.advance(state,{assessment:assessment('continue',['Independent follow-up'])}),error=>
    error.name==='CapacityExceeded'&&error.mode==='debug'&&error.dimension==='research_rounds'&&error.actual===2&&error.limit===1);
  assert.equal(records.length,before);
});

test('debug deadline raises typed capacity and stops a waiting execution port',async()=>{
  const runtime=new ResearchRuntime(ports({executeRound:()=>new Promise(()=>{})}),{runtimeLimitMode:'debug'});
  await assert.rejects(runtime.advance(runtime.init(plan),{deadline:Date.now()+10}),error=>
    error.name==='CapacityExceeded'&&error.mode==='debug'&&error.dimension==='tool_timeout_seconds');
});

test('unknown phase, invalid continuation and absent real output cannot complete',async()=>{
  const runtime=new ResearchRuntime(ports({inspectProducts:async()=>({ready:false,actualProductRefs:[],limitations:['Report missing']})}));
  assert.throws(()=>restoreSnapshot(JSON.stringify({...runtime.init(plan),phase:'invented'})),/phase/);
  let state=await reachQuestion(runtime,runtime.init(plan));
  await assert.rejects(runtime.advance(state,{assessment:assessment('continue')}),/follow-up/);
  state=(await runtime.advance(state,{assessment:assessment('deliver')})).snapshot;
  state=(await runtime.advance(state)).snapshot;
  const missing=await runtime.advance(state);
  assert.equal(missing.status,'needs_products');assert.equal(missing.snapshot.phase,'saving');
});

test('retained upstream default executes real injected search -> extract -> follow-up -> report phases',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'pinned-research-')); const searched=[];
  const resolver=new UpstreamProfileResolver({},'default');
  const originalPlan={topic:'A source question',goal:'Resolve the source question',researchQuestions:['Initial question'],
    engines:['duckduckgo'],enabledEngines:['duckduckgo'],profile:{name:'default'},
    scope:{include:'source',exclude:''},estimatedCost:{searchCalls:0,scrapeCalls:0,description:''}};
  const machine=new UpstreamResearchStateMachine({
    searchFn:async question=>{searched.push(question);return [{title:question,url:'https://example.test/'+searched.length,snippet:'Actual injected result',engine:'fixture'}];},
    scraper:{scrape:async url=>({url,title:'Source',content:'Injected source content'})},
    profileResolver:resolver,logger:{event(){}},artifactsDir:dir,
  });
  try {
    let state=UpstreamResearchStateMachine.init(originalPlan,resolver,'pinned-run');
    state=(await machine.next(state,originalPlan)).snapshot;
    assert.equal(state.phase,'extracting');assert.equal(state.currentDepth,1);
    state=(await machine.next(state,originalPlan,'Source extraction')).snapshot;
    assert.equal(state.phase,'questioning');
    state=(await machine.next(state,originalPlan,'1. Which source explains the observed conflict?')).snapshot;
    assert.equal(state.phase,'extracting');assert.equal(state.currentDepth,2);
    assert.deepEqual(searched,['Initial question','Which source explains the observed conflict?']);
    state=(await machine.next(state,originalPlan)).snapshot;assert.equal(state.phase,'drafting');
    const report='A retained complete report from the existing model session with source citations.';
    state=(await machine.next(state,originalPlan,report)).snapshot;assert.equal(state.phase,'saving');
    state=(await machine.next(state,originalPlan)).snapshot;assert.equal(state.phase,'done');
    assert.equal(state.draft.get(),report);
  }finally{await rm(dir,{recursive:true,force:true});}
});

test('deadline cancels waiting work and returns no fabricated result',async()=>{
  const runtime=new ResearchRuntime(ports({executeRound:async()=>new Promise(()=>{})}));
  await assert.rejects(runtime.advance(runtime.init(plan),{deadline:Date.now()+10}),{name:'TimeoutError'});
});

test('uncertain assessment receipt recovers the supplied decision without reevaluation',async()=>{
  let assessments=0, writes=0;const identities=[];
  const runtime=new ResearchRuntime(ports({
    assess:async({suppliedAssessment})=>{assessments++;return suppliedAssessment;},
    recordResult:async({recordId,kind})=>{
      if(kind==='assessment'){identities.push(recordId);if(++writes===1)throw new Error('receipt not confirmed');}
      return {checkpointRef:'checkpoint',revision:1};
    },
  }));
  const state=await reachQuestion(runtime,runtime.init(plan));
  const pending=await runtime.advance(state,{assessment:assessment('deliver')});
  assert.equal(pending.status,'record_pending');
  const resumed=await runtime.advance(restoreSnapshot(serializeSnapshot(pending.snapshot)));
  assert.equal(resumed.snapshot.phase,'drafting');assert.equal(assessments,1);
  assert.deepEqual(identities,['run-1:1:assessment','run-1:1:assessment']);
});
