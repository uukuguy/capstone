import test from 'node:test';
import assert from 'node:assert/strict';
import { configureResearchGuidance } from '../src/capstone_agent/resources/research-guidance.mjs';

test('guidance starts before work and follows the first result without a call-count threshold', async () => {
  const hooks = {};
  configureResearchGuidance({on: (name, fn) => { hooks[name] = fn; }}, 'Record findings and remaining work.');
  const messages = [{role:'user',content:'original goal'}];
  const result = await hooks.context({messages});
  assert.equal(result.messages.length,2);
  assert.equal(result.messages[0],messages[0]);
  assert.match(result.messages[1].content,/Record findings/);
  assert.equal(await hooks.context({messages}),undefined);
  hooks.tool_execution_end({toolName:'read'});
  assert.equal((await hooks.context({messages})).messages.length,2);
  for(let i=0;i<20;i++) hooks.tool_execution_end({toolName:'bash'});
  assert.equal(await hooks.context({messages}),undefined);
});

test('a failure prompts a public limitation; only confirmed progress clears the reminder', async () => {
  const hooks={};
  configureResearchGuidance({on:(name,fn)=>{hooks[name]=fn;}},'Record findings.');
  const messages=[];
  await hooks.context({messages});
  hooks.tool_execution_end({toolName:'bash',isError:true});
  hooks.tool_execution_end({toolName:'agent_task_progress',isError:false,result:{details:{ok:false}}});
  assert.ok(await hooks.context({messages}));
  hooks.tool_execution_end({toolName:'bash',isError:true});
  hooks.tool_execution_end({toolName:'agent_task_progress',isError:false,result:{details:{ok:true,result:{kind:'limitation'}}}});
  assert.equal(await hooks.context({messages}),undefined);
});

test('a goal receipt after the first source result does not suppress its observation reminder', async () => {
  const hooks={};
  configureResearchGuidance({on:(name,fn)=>{hooks[name]=fn;}},'Record findings.');
  const messages=[];
  await hooks.context({messages});
  hooks.tool_execution_end({toolName:'read',isError:false});
  hooks.tool_execution_end({toolName:'agent_task_progress',isError:false,
    result:{details:{ok:true,result:{kind:'goal'}}}});
  assert.ok(await hooks.context({messages}));
  assert.equal(await hooks.context({messages}),undefined);
  hooks.tool_execution_end({toolName:'bash',isError:true});
  hooks.tool_execution_end({toolName:'agent_task_progress',isError:false,
    result:{details:{ok:true,result:{kind:'goal'}}}});
  assert.ok(await hooks.context({messages}));
  hooks.tool_execution_end({toolName:'bash',isError:true});
  hooks.tool_execution_end({toolName:'agent_task_progress',isError:false,
    result:{details:{ok:true,result:{kind:'observation'}}}});
  assert.equal(await hooks.context({messages}),undefined);
});

test('ordinary execution has no research reminders', () => {
  let registered=false;
  configureResearchGuidance({on:()=>{registered=true;}},undefined);
  assert.equal(registered,false);
});

test('a confirmed goal acknowledges the initial reminder without adding a new request', async () => {
  const hooks={};
  configureResearchGuidance({on:(name,fn)=>{hooks[name]=fn;}},'Record findings.');
  hooks.tool_execution_end({toolName:'agent_task_progress',isError:false,
    result:{details:{ok:true,result:{kind:'goal'}}}});
  assert.equal(await hooks.context({messages:[]}),undefined);
});
