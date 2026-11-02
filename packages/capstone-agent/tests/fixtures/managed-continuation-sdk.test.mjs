import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,realpath,mkdir,readFile,rm,access} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {createManagedChildSession,runSettledPrompt} from '../../src/capstone_agent/resources/general-sdk.mjs';
const root=fileURLToPath(new URL('../../../../',import.meta.url));

for(const mode of ['stalled','actual-repair'])test('generic actual SDK continuation: '+mode,{timeout:15000},async()=>{
  const sdk=await import(pathToFileURL(join(root,'.grid-agent/runtime/pi/source/packages/coding-agent/dist/index.js')).href);
  const ai=await import(pathToFileURL(join(root,'.grid-agent/runtime/pi/source/packages/ai/dist/index.js')).href);
  const dir=await realpath(await mkdtemp(join(tmpdir(),'managed-continuation-')));
  const cwd=process.cwd(),oldAgent=process.env.PI_CODING_AGENT_DIR;
  const agent=join(dir,'.agent');await mkdir(agent);
  let child,turn=0;
  const events=[];
  const model={id:'offline-continuation',name:'Offline continuation',provider:'capstone-general',api:'openai-completions',
    baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,
    cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
  const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
    streamSimple(){
      if(turn>3)throw new Error('Fixture detected unbounded generic continuation');
      const content=mode==='actual-repair'&&turn===1?[{type:'toolCall',id:'actual-write',name:'write',arguments:{path:'retained.md',content:'Actual saved work\n'}}]:
        [{type:'text',text:'A model response without a new action.'}];
      turn++;
      const message={role:'assistant',content,api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),
        usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}},
        stopReason:content[0].type==='toolCall'?'toolUse':'stop'};
      const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
    }};
  try {
    process.chdir(dir);process.env.PI_CODING_AGENT_DIR=agent;
    child=await createManagedChildSession({model:model.id,settings:{compaction:{enabled:false}},extensions:[],allowedSkills:[],
      contextFiles:[],applicationPolicy:{allowed_tools:['read','write']}},sdk,runtime,{toolNames:['read','write'],cwd:dir});
    const continuation=async()=>{
      if(mode==='actual-repair'){
        try{await access(join(dir,'retained.md'));return null;}catch{}
      }
      return {prompt:'Perform the authorized pending action now.',actionId:'stable-action',checkpoint:'stable-checkpoint'};
    };
    const run=runSettledPrompt(child.session,{kind:'text',text:'Complete authorized work'},null,event=>events.push(event),continuation);
    if(mode==='stalled') {
      await assert.rejects(run,error=>error.code==='continuation_no_progress'&&/saved outputs were retained/.test(error.message));
      assert.equal(turn,2);
      const failed=events.filter(event=>event.type==='agent_end');
      assert.equal(failed.length,1);assert.equal(failed[0].success,false);
      assert.equal(failed[0].code,'continuation_no_progress');assert.equal(failed[0].messages.length,2);
      assert.ok(failed[0].messages.every(message=>message.stopReason==='stop'&&message.usage));
    }else {
      await run;assert.equal(turn,3);
      assert.equal(await readFile(join(dir,'retained.md'),'utf8'),'Actual saved work\n');
      assert.equal(events.filter(event=>event.type==='agent_end').length,1);
      assert.ok(events.some(event=>event.type==='tool_execution_end'&&event.toolName==='write'));
    }
  }finally {
    await child?.close();process.chdir(cwd);
    if(oldAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=oldAgent;
    await rm(dir,{recursive:true,force:true});
  }
});
