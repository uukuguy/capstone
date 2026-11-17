import test from 'node:test';
import assert from 'node:assert/strict';
import {createInstructionSteering} from '../src/capstone_agent/resources/general-sdk.mjs';

test('steering acknowledges actual user message consumption, with stable identity', async()=>{
 let observe; const queued=[], receipts=[];
 const session={subscribe(fn){observe=fn;return ()=>{};},async steer(text){queued.push(text);}};
 const steering=createInstructionSteering(session,{},event=>receipts.push(event));
 const frame={type:'steer',instruction_id:'instruction-1',text:'/skill:other keep the prior result'};
 await steering.accept(JSON.stringify(frame));
 await steering.accept(JSON.stringify(frame));
 assert.equal(queued.length,1);assert.equal(receipts.length,0);
 observe({type:'message_start',message:{role:'assistant',content:queued[0]}});
 assert.equal(receipts.length,0);
 observe({type:'message_start',message:{role:'user',content:[{type:'text',text:queued[0]}]}});
 assert.deepEqual(receipts,[{type:'general_pi_instruction_consumed',instruction_id:'instruction-1'}]);
 await assert.rejects(steering.accept(JSON.stringify({...frame,text:'changed'})),/identity/);
 steering.close();
 await assert.rejects(steering.accept(JSON.stringify({...frame,instruction_id:'later'})),/closed/);
});

test('steering rejects grant fields and invalid or unbounded text',async()=>{
 const steering=createInstructionSteering({subscribe(){return ()=>{}},async steer(){}},{},()=>{});
 for(const frame of [{type:'steer',instruction_id:'x',text:'ok',grants:[]},
   {type:'steer',instruction_id:'x',text:''},{type:'steer',instruction_id:'x',text:'x'.repeat(2000000)}]){
  await assert.rejects(steering.accept(JSON.stringify(frame)));
 }
 steering.close();
});
