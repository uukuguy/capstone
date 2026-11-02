// Offline evidence for the pinned SDK seams. No model or enterprise tool calls.
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { ExtensionRunner } from '../../packages/pi-grid-tools/node_modules/@earendil-works/pi-coding-agent/dist/core/extensions/runner.js';
import { SessionManager } from '../../packages/pi-grid-tools/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js';
import { AgentSession } from '../../packages/pi-grid-tools/node_modules/@earendil-works/pi-coding-agent/dist/core/agent-session.js';

const calls=[];
const runner={createContext:()=>({}),extensions:[
  {handlers:new Map([['tool_call',[(e)=>{e.input.path='changed';calls.push('mutate')}]]])},
  {handlers:new Map([['tool_call',[(e)=>{assert.equal(e.input.path,'changed');calls.push('guard');return {block:true,reason:'design probe'}}]]])},
  {handlers:new Map([['tool_call',[()=>calls.push('must-not-run')]]])},
]};
assert.equal((await ExtensionRunner.prototype.emitToolCall.call(runner,{type:'tool_call',toolName:'read',toolCallId:'t1',input:{path:'initial'}})).block,true);
assert.deepEqual(calls,['mutate','guard']);
for(const name of ['steer','abort'])assert.equal(typeof AgentSession.prototype[name],'function');
const directory=mkdtempSync(join(tmpdir(),'capstone-design-probe-'));
try {
  const manager=SessionManager.create(directory,directory);
  manager.appendMessage({role:'user',content:'offline checkpoint probe',timestamp:Date.now()});
  manager.appendMessage({role:'assistant',content:[{type:'text',text:'offline fixture response'}],api:'openai-responses',provider:'fixture',model:'fixture',usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}},stopReason:'stop',timestamp:Date.now()});
  const reopened=SessionManager.open(manager.getSessionFile());
  assert.equal(reopened.buildSessionContext().messages.length,2);
  console.log('PASS: ordered pre-tool block; mutable arguments observed; persisted session reopen; steer/abort entry points exist. Full bridge integration is not tested.');
} finally {rmSync(directory,{recursive:true,force:true})}
