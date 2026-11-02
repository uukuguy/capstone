import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {checkCapacity,runtimeLimits} from '../src/capstone_agent/resources/runtime-limits.mjs';

for(const mode of ['normal','debug'])test(`managed SDK repairs oversized tool input in the same ${mode} task`,async()=>{
  const root=resolve('.grid-agent/runtime/pi/source/packages');
  const sdk=await import(pathToFileURL(resolve(root,'coding-agent/dist/index.js')).href);
  const ai=await import(pathToFileURL(resolve(root,'ai/dist/index.js')).href);
  const adapter=await import('../src/capstone_agent/resources/general-sdk.mjs');
  const cwd=await mkdtemp(resolve(tmpdir(),'capacity-repair-')),previous=process.env.PI_CODING_AGENT_DIR,previousCwd=process.cwd();
  const limits=runtimeLimits({command_bytes:8},{mode}),executed=[];
  const boundedSdk={...sdk,createCodingTools:()=>[{name:'bash',label:'Bounded command',description:'Execute a bounded command',
    parameters:{type:'object',properties:{command:{type:'string'}},required:['command']},
    async execute(_id,args){checkCapacity(limits,'command_bytes',Buffer.byteLength(args.command),'bytes','tool_arguments');
      executed.push(args.command);return {content:[{type:'text',text:'Saved'}],details:{}};}}]};
  const model={id:'capacity-offline',name:'Offline',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
  let turn=0,owned;
  const diagnostics=[],write=process.stderr.write;
  const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
    streamSimple(_model,context){
      const results=context.messages.filter(message=>message.role==='toolResult');
      if(turn===1){assert.equal(results.at(-1).isError,true);assert.match(JSON.stringify(results.at(-1)),/command_bytes/);assert.deepEqual(executed,[]);}
      if(turn===2)assert.equal(results.at(-1).isError,false);
      const content=turn<2?[{type:'toolCall',id:`call-${turn}`,name:'bash',arguments:{command:turn===0?'x'.repeat(9):'valid'}}]:[{type:'text',text:'Completed.'}];
      const message={role:'assistant',content,api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),stopReason:turn++<2?'toolUse':'stop',usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}};
      const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
    }};
  const originalStream=runtime.streamSimple;
  try{
    process.stderr.write=function(chunk,...args){
      if(String(chunk).includes('"type":"capacity_diagnostic"')){diagnostics.push(String(chunk));return true;}
      return write.call(this,chunk,...args);
    };
    process.chdir(cwd);
    process.env.PI_CODING_AGENT_DIR=resolve(cwd,'agent');await mkdir(process.env.PI_CODING_AGENT_DIR);
    const config={model:model.id,runtimeLimitMode:mode,settings:{packages:[],extensions:[],skills:[]},extensions:[],allowedSkills:[],contextFiles:[],systemPrompt:'Use the bounded tool.',applicationPolicy:{allowed_tools:['bash']}};
    owned=await adapter.createManagedChildSession(config,boundedSdk,runtime,{toolNames:['bash'],cwd});
    await owned.session.prompt('Save the result.');
    assert.equal(turn,3);assert.deepEqual(executed,['valid']);assert.equal(runtime.streamSimple,originalStream);
    assert.equal(diagnostics.length,mode==='debug'?1:0);
    if(mode==='debug'){
      assert.ok(Buffer.byteLength(diagnostics[0])<1024);
      assert.deepEqual(JSON.parse(diagnostics[0]),{type:'capacity_diagnostic',code:'capacity_exceeded',mode:'debug',dimension:'command_bytes',actual:9,limit:8,unit:'bytes',phase:'tool_arguments'});
    }
    await owned.close();
    assert.throws(()=>checkCapacity(limits,'command_bytes',9,'bytes','after_close'));
    assert.equal(diagnostics.length,mode==='debug'?1:0);
  }finally{await owned?.close();process.stderr.write=write;process.chdir(previousCwd);if(previous===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=previous;await rm(cwd,{recursive:true,force:true});}
});

test('native prompt frame accepts configured capacity above old fixed frame bound', async () => {
  const {validatePromptFrame} = await import('../src/capstone_agent/resources/general-sdk.mjs');
  const text = '字'.repeat(100000);
  const line = JSON.stringify({type: 'prompt', message: text});
  const frame = validatePromptFrame(line, {input: {kind: 'text', text},
    runtimeLimits: {rpc_frame_bytes: 400000, input_text_chars: 100000}});
  assert.equal(frame.message, text);
});

test('native prompt frame applies exact bytes and Unicode input character overrides', async () => {
  const {validatePromptFrame} = await import('../src/capstone_agent/resources/general-sdk.mjs');
  const text = '🙂'.repeat(11);
  const line = JSON.stringify({type: 'prompt', message: text});
  assert.throws(() => validatePromptFrame(line, {input: {kind: 'text', text},
    runtimeLimits: {rpc_frame_bytes: Buffer.byteLength(line) - 1, input_text_chars: 20}}),
  error => error.capacity.dimension === 'rpc_frame_bytes' && error.capacity.actual === Buffer.byteLength(line));
  assert.throws(() => validatePromptFrame(line, {input: {kind: 'text', text},
    runtimeLimits: {rpc_frame_bytes: 1000, input_text_chars: 10}}),
  error => error.capacity.dimension === 'input_text_chars' && error.capacity.actual === 11 && error.capacity.limit === 10);
  assert.equal(validatePromptFrame(line, {input: {kind: 'text', text},
    runtimeLimits: {rpc_frame_bytes: Buffer.byteLength(line), input_text_chars: 11}}).message, text);
});
