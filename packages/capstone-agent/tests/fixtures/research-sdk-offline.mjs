// Script only model output. The real SDK executes every tool and request hook.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {resolve, dirname} from 'node:path';
const config = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const sdk = await import(pathToFileURL(config.sdk).href);
const ai = await import(pathToFileURL(resolve(dirname(config.sdk), '../../ai/dist/index.js')).href);
const {runManagedSession} = await import(pathToFileURL(process.argv[3]).href);
const files = config.contextFiles.filter(file => file.path.endsWith('.csv'));
assert.equal(files.length, 2);
const sources = files.map(file => file.content.match(/material:material_[a-f0-9]{32}:[a-f0-9]{64}/)[0]);
const previous = JSON.parse(readFileSync(resolve(config.researchChannelPath, 'view.json'), 'utf8')).state;
const continuation = previous?.revision === 2;
const model = {id: config.model, name: 'Offline research', provider: 'capstone-general',
 api: 'openai-completions', baseUrl: 'http://127.0.0.1:1', reasoning: false,
 input: ['text'], contextWindow: 32000, maxTokens: 1024,
 cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0}};
let round = 0;
const tool = (id, name, arguments_) => ({type:'toolCall',id,name,arguments:arguments_});
const runtime = {getModel:()=>model, hasConfiguredAuth:()=>true,
 getAuth:async()=>({auth:{apiKey:'offline-fixture'}}), isUsingOAuth:()=>false,
 streamSimple(_model, context) {
  assert.match(context.systemPrompt, /agent_research_update/);
  assert.match(context.systemPrompt, /Research methods and source checks/);
  const summaries = context.messages.filter(message => JSON.stringify(message.content).includes('Committed research state (agent judgments'));
  if (continuation || round >= 2) {
   assert.equal(summaries.length, 1, 'exactly one committed summary before model request');
   const revision = continuation ? (round < 2 ? 2 : 3) : (round === 2 ? 1 : 2);
   assert.match(JSON.stringify(summaries[0]), new RegExp('research_revision[^0-9]*' + revision));
  }
  const results = context.messages.filter(message => message.role === 'toolResult');
  const observed = id => JSON.stringify(results.find(message => message.toolCallId === id)?.content);
  let content;
  if (continuation) {
   if (round === 0) content = [tool('read-followup','read',{path:files[1].path})];
   else if (round === 1) {
    const observedRef = observed('read-followup').match(/native-observation:pi-[a-f0-9]{64}:[a-f0-9]{64}/)[0];
    content = [tool('research-followup','agent_research_update',{expected_revision:2,changes:{
     claims:[...previous.claims,{claim_id:'followup',statement:'The second source still gives 84',status:'supported',refs:[observedRef]}]}})];
   } else content = [{type:'text',text:'Prior source-backed claim retained; the second source remains 84.'}];
  } else if (round === 0) content = [tool('read-a','read',{path:files[0].path}),
    tool('progress','agent_task_progress',{kind:'goal',text:'Compare both source versions'})];
  else if (round === 1) {
   assert.match(observed('read-a'), /42/);
   assert.ok(config.researchGuidance);
   assert.ok(context.messages.some(message => message.role === 'user'
    && (typeof message.content === 'string' ? message.content === config.researchGuidance
      : message.content.some(block => block.type === 'text' && block.text === config.researchGuidance))),
    'a goal receipt after reading does not suppress the next source-observation reminder');
   content = [tool('research-one','agent_research_update',{expected_revision:0, changes:{goal:'Compare the supplied sources',
    claims:[{claim_id:'value',statement:'First source gives 42',status:'supported',refs:[sources[0]]}]} }),
    tool('read-b','read',{path:files[1].path})];
  } else if (round === 2) {
   assert.match(observed('read-b'), /84/);
   const observedRef = observed('read-b').match(/native-observation:pi-[a-f0-9]{64}:[a-f0-9]{64}/)?.[0];
   assert.ok(observedRef, 'fresh real tool result supplies a host-bound source reference');
   content = [tool('research-two','agent_research_update',{expected_revision:1, changes:{
    claims:[{claim_id:'value',statement:'A single consistent value is not established: sources give 42 and 84',status:'refuted',refs:[sources[0],observedRef]}],
    open_questions:['Which source is current?'], notes:[{note_id:'method-change',text:'Retain both source values; ask for the current version instead of averaging.',refs:sources}]} })];
  } else if (round === 3) content = [tool('report','write',{path:'comparison.md',content:'# Source comparison\nA: 42\nB: 84\nThe sources disagree; the current version is unresolved.\n'})];
  else content = [{type:'text',text:'The sources give 42 and 84. The current version is unresolved. See comparison.md.'}];
  round++;
  const message = {role:'assistant',content,api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),
   usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}},
   stopReason:content.some(item=>item.type==='toolCall')?'toolUse':'stop'};
  const stream=ai.createAssistantMessageEventStream();
  stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
 }};
await runManagedSession(config, sdk, runtime).catch(error => {
 writeFileSync('offline-error.txt', String(error.stack)); throw error;
});
assert.equal(round, continuation ? 3 : 5);
