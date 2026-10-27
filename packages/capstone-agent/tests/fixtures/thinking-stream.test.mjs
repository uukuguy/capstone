import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {mkdtemp,mkdir,readFile,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {rpcEvent} from '../../src/capstone_agent/resources/general-sdk.mjs';
import {configureModelRequestCapture} from '../../src/capstone_agent/resources/model-request-capture.mjs';

test('failed response boundaries retain safe error classification without provider text',()=>{
  const message={role:'assistant',stopReason:'error',errorMessage:'400 Input token length is too long; api_key=secret-canary',content:[]};
  const frame=rpcEvent({type:'message_end',message});
  assert.equal(frame.message.errorCode,'model_context_limit');
  assert.equal(frame.message.errorStatus,400);
  assert.doesNotMatch(JSON.stringify(frame),/secret-canary|api_key|Input token/);
  const terminal=rpcEvent({type:'agent_end',messages:[message]});
  assert.equal(terminal.messages[0].errorCode,'model_context_limit');
});

test('actual pinned SDK streams supplied thinking with reasoning false while capture stays redacted',async()=>{
  const ai=await import(pathToFileURL(resolve(import.meta.dirname,'../../../../.grid-agent/runtime/pi/source/packages/ai/dist/api/openai-completions.js')).href);
  const root=await mkdtemp(join(tmpdir(),'public-thinking-'));
  let request;
  const server=createServer(async(req,res)=>{
    const body=[];for await(const part of req)body.push(part);request=JSON.parse(Buffer.concat(body).toString());
    res.writeHead(200,{'Content-Type':'text/event-stream'});
    for(const delta of [
      {role:'assistant',reasoning_content:'Check the inputs. '},
      {reasoning_content:'Choose the next step.',reasoning_details:[{type:'reasoning.encrypted',data:'PRIVATE_REPLAY_METADATA'}]},
      {content:'Final answer.'},
    ])res.write('data: '+JSON.stringify({id:'fixture',object:'chat.completion.chunk',model:'fixture',
      choices:[{index:0,delta,finish_reason:null}]})+'\n\n');
    res.write('data: '+JSON.stringify({id:'fixture',choices:[{index:0,delta:{},finish_reason:'stop'}]})+'\n\n');
    res.end('data: [DONE]\n\n');
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  try{
    const model={id:'fixture',name:'Fixture',provider:'fixture',api:'openai-completions',
      baseUrl:'http://127.0.0.1:'+server.address().port+'/v1',reasoning:false,input:['text'],
      contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
    const stream=ai.streamSimple(model,{messages:[{role:'user',content:'Inspect these inputs.',timestamp:0}]},
      {apiKey:'offline-fixture',maxRetries:0});
    const frames=[];for await(const event of stream)frames.push(rpcEvent({type:'message_update',assistantMessageEvent:event}));
    const message=await stream.result();
    assert.equal(message.stopReason,'stop');
    assert.equal(frames.filter(frame=>frame.assistantMessageEvent.type==='thinking_delta')
      .map(frame=>frame.assistantMessageEvent.delta).join(''),'Check the inputs. Choose the next step.');
    assert.equal(frames.filter(frame=>frame.assistantMessageEvent.type==='text_delta')
      .map(frame=>frame.assistantMessageEvent.delta).join(''),'Final answer.');
    assert.ok(frames.every(frame=>Object.keys(frame.assistantMessageEvent).every(key=>['type','delta'].includes(key))));
    assert.doesNotMatch(JSON.stringify(frames),/PRIVATE_REPLAY_METADATA/);
    assert.equal(model.reasoning,false);
    assert.equal(request.reasoning_effort,undefined);

    const activeTurnPath=join(root,'active.json'),captureStatePath=join(root,'state.json'),requestsPath=join(root,'requests');
    await mkdir(requestsPath);
    await writeFile(activeTurnPath,JSON.stringify({turn_id:'turn-thinking'}));
    await writeFile(captureStatePath,JSON.stringify({source_event_sequences:[1],context_revision:1,context_state_hash:'0'.repeat(64)}));
    const hooks=new Map();
    configureModelRequestCapture({on:(name,handler)=>hooks.set(name,handler)},
      {activeTurnPath,captureStatePath,requestsPath},message=>{throw new Error(message);});
    await hooks.get('before_model_request')({type:'before_model_request',model,context:{messages:[message]},options:{}});
    const saved=await readFile(join(requestsPath,'turn-thinking-r001','input.json'),'utf8');
    assert.deepEqual(JSON.parse(saved).semantic_request.context.messages[0].content[0],{type:'thinking',redacted:true});
    assert.doesNotMatch(saved,/Check the inputs|Choose the next step|PRIVATE_REPLAY_METADATA/);
    assert.match(saved,/Final answer/);
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));await rm(root,{recursive:true,force:true});}
});
