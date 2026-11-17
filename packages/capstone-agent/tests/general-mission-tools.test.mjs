import test from 'node:test';
import assert from 'node:assert/strict';
import {createMissionTools} from '../src/capstone_agent/resources/mission-tools.mjs';

test('Mission transport waits for the bound Control receipt and never accepts caller origins',async()=>{
 const calls=[];let polls=0;
 const tools=createMissionTools({deadlineAt:Date.now()+1000,missionTools:{url:'http://host/mission-tools/task',grant:'private',
  catalog:{agent_mission_read:{description:'Read',inputSchema:{type:'object',properties:{},additionalProperties:false}}}}},{fetchImpl:async(url,options)=>{
   calls.push({url,body:JSON.parse(options.body)});
   return {ok:true,json:async()=>++polls===1?{pending:true}:{call_id:'call-1',is_error:false,result:{mission_id:'goal_1',state:'planning'}}};
  }});
 const result=await tools[0].execute('call-1',{},new AbortController().signal);
 assert.deepEqual(calls.map(c=>c.body),Array(2).fill({call_id:'call-1',name:'agent_mission_read',arguments:{}}));
 assert.equal(result.details.ok,true);assert.match(result.content[0].text,/planning/);
});

test('Mission transport fails closed on a receipt for another call',async()=>{
 const tools=createMissionTools({deadlineAt:Date.now()+1000,missionTools:{url:'http://host',grant:'private',
  catalog:{agent_mission_read:{inputSchema:{type:'object'}}}}},{fetchImpl:async()=>({ok:true,json:async()=>({call_id:'other',result:{},is_error:false})})});
 await assert.rejects(tools[0].execute('call-1',{}),/receipt/);
});
