import test from 'node:test';
import assert from 'node:assert/strict';
import { configureResearchGuidance } from '../src/capstone_agent/resources/research-guidance.mjs';

test('lightweight progress guidance does not append a synthetic user request after the real instruction', () => {
  const hooks={};
  configureResearchGuidance({on:(name,fn)=>{hooks[name]=fn;}},'Report completed/current/gap progress.',{lightweight:true});
  assert.equal(hooks.context({messages:[{role:'user',content:'actual instruction'}]}),undefined);
  const result=hooks.before_agent_start({systemPrompt:'Application policy.'});
  assert.match(result.systemPrompt,/Application policy/);
  assert.match(result.systemPrompt,/Report completed\/current\/gap progress/);
  assert.match(result.systemPrompt,/not a new user request/);
});

test('lightweight checkpoints coalesce at model boundaries without new user messages', () => {
  const hooks={};
  configureResearchGuidance({on:(name,fn)=>{hooks[name]=fn;}},'Progress.',{lightweight:true,checkpointCalls:3});
  const start=()=>hooks.before_agent_start({systemPrompt:'Base policy.'}).systemPrompt;
  const messages=[{role:'user',content:'actual instruction'},{role:'toolResult',toolCallId:'last',content:[{type:'text',text:'source result'}]}];
  const review=()=>hooks.context({messages});
  assert.match(start(),/finite scope/);
  assert.match(start(),/not.*budget guarantee/);
  const end=(id,details)=>hooks.tool_execution_end({toolCallId:id,result:{details}});
  end('a');end('b');
  assert.equal(review(),undefined);
  end('b'); // duplicate SDK delivery must not count twice
  assert.equal(review(),undefined);
  end('c');end('d');end('e');end('f');
  const result=review();
  assert.equal(result.messages.length,2);
  assert.equal(result.messages[0],messages[0]);
  assert.equal(messages[1].content.length,1);
  const note=result.messages[1].content.at(-1).text;
  assert.match(note,/Scope review checkpoint/);
  assert.match(note,/6 completed leaf calls/);
  assert.match(note,/sampled absence/);
  assert.match(note,/requested/);
  assert.equal(review().messages[1].content.at(-1).text,note);
  hooks.message_end({message:{role:'assistant',stopReason:'error'}});
  assert.equal(review().messages[1].content.at(-1).text,note);
  hooks.message_end({message:{role:'assistant',stopReason:'toolUse'}});
  assert.equal(review(),undefined);
});

test('composition receipt counts only completed leaves and zero-leaf programs do not count as calls', () => {
  const hooks={};
  configureResearchGuidance({on:(name,fn)=>{hooks[name]=fn;}},'Progress.',{lightweight:true,checkpointCalls:3});
  const messages=[{role:'toolResult',toolCallId:'last',content:[{type:'text',text:'source result'}]}];
  const review=()=>hooks.context({messages});
  const receipt=n=>({kind:'capstone-tool-composition/1',completed_leaf_calls:n});
  hooks.tool_execution_end({toolCallId:'wrapper-empty',result:{details:receipt(0)}});
  hooks.tool_execution_end({toolCallId:'wrapper',result:{details:receipt(2)}});
  assert.equal(review(),undefined);
  hooks.tool_execution_end({toolCallId:'failed',isError:true,result:{details:receipt(1)}});
  assert.match(review().messages[0].content.at(-1).text,/3 completed leaf calls/);
  hooks.message_end({message:{role:'assistant',stopReason:'stop'}});
  hooks.tool_execution_end({toolCallId:'pending',result:{details:receipt(4)}});
  hooks.session_start();
  assert.equal(review(),undefined);
});

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
