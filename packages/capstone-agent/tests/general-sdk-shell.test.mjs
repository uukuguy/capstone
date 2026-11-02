import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import * as adapter from '../src/capstone_agent/resources/general-sdk.mjs';

test('isolated native standard SDK bash preserves pipeline failures and explicit recovery semantics',async()=>{
 const sdk=await import(pathToFileURL(resolve('.grid-agent/runtime/pi/source/packages/coding-agent/dist/index.js')).href);
 const cwd=await mkdtemp(resolve(tmpdir(),'native-pipefail-'));
 try{
  const bash=adapter.createIsolatedNativeTools(sdk,cwd).find(tool=>tool.name==='bash');
  await assert.rejects(bash.execute('upstream',{command:'false | tail -n 1'}),/code 1/);
  assert.match(JSON.stringify(await bash.execute('normal',{command:"printf 'one\\ntwo\\n' | tail -n 1"})),/two/);
  assert.match(JSON.stringify(await bash.execute('recover',{command:"false | tail -n 1 || printf recovered"})),/recovered/);
  assert.match(JSON.stringify(await bash.execute('text',{command:"printf 'Traceback (most recent call last):\\n'"})),/Traceback/);
  await assert.rejects(bash.execute('sigpipe',{command:'yes data | head -n 1'}),/code 141/);
  assert.match(JSON.stringify(await bash.execute('no-errexit',{command:'false; printf continued'})),/continued/);
  assert.match(JSON.stringify(await bash.execute('multiline',{command:"# initial user comment\nprintf '%s\\n' first | tail -n 1\nprintf '%s\\n' second # trailing comment"})),/first[\s\S]*second/);
 }finally{await rm(cwd,{recursive:true,force:true});}
});

test('actual managed child session receives the same pipefail tools and shell guidance',async()=>{
 const sdkRoot=resolve('.grid-agent/runtime/pi/source/packages');
 const sdk=await import(pathToFileURL(resolve(sdkRoot,'coding-agent/dist/index.js')).href);
 const ai=await import(pathToFileURL(resolve(sdkRoot,'ai/dist/index.js')).href);
 const cwd=await mkdtemp(resolve(tmpdir(),'child-pipefail-')),previousCwd=process.cwd(),previousAgent=process.env.PI_CODING_AGENT_DIR;
 const commands=[['false | tail -n 1',true], ["printf normal | tail -n 1",false],
   ['false | tail -n 1 || printf recovered',false], ["printf 'Traceback: ordinary text'",false],
   ['yes data | head -n 1',true], ['false; printf continued',false]];
 const model={id:'shell-offline',name:'Offline',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',
   reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
 let turn=0,owned;
 const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
  streamSimple(_model,context){
   assert.match(context.systemPrompt,/pipefail/);assert.match(context.systemPrompt,/Errexit is not enabled/);
   const results=context.messages.filter(message=>message.role==='toolResult');
   if(turn)assert.equal(results.at(-1).isError,commands[turn-1][1],commands[turn-1][0]);
   const content=turn<commands.length?[{type:'toolCall',id:'shell-'+turn,name:'bash',arguments:{command:commands[turn][0]}}]:[{type:'text',text:'Shell behavior verified.'}];
   turn++;
   const message={role:'assistant',content,api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),
    stopReason:turn<=commands.length?'toolUse':'stop',usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}};
   const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
  }};
 try{
  process.chdir(cwd);process.env.PI_CODING_AGENT_DIR=resolve(cwd,'agent');await mkdir(process.env.PI_CODING_AGENT_DIR);
  const config={model:model.id,settings:{packages:[],extensions:[],skills:[]},extensions:[],allowedSkills:[],contextFiles:[],
   systemPrompt:'Use authorized shell tools.',applicationPolicy:{allowed_tools:['bash']}};
  owned=await adapter.createManagedChildSession(config,sdk,runtime,{toolNames:['bash'],cwd});
  await owned.session.prompt('Verify each shell command.');assert.equal(turn,commands.length+1);
 }finally{
  await owned?.close();process.chdir(previousCwd);
  if(previousAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=previousAgent;
  await rm(cwd,{recursive:true,force:true});
 }
});
