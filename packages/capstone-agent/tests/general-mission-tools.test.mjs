import test from 'node:test';
import assert from 'node:assert/strict';
import {createMissionTools} from '../src/capstone_agent/resources/mission-tools.mjs';
import {createToolDiscovery} from '../src/capstone_agent/resources/general-tool-discovery.mjs';

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

test('a Mission-denied published tool cannot reenter discovery or the runtime tool list',async()=>{
 const publications=Object.fromEntries(['published_read','published_write'].map(name=>[name,{description:name,inputSchema:{type:'object',properties:{}}}]));
 const tools=Object.entries(publications).map(([name,p])=>({name,parameters:p.inputSchema,execute:async()=>({content:[]})}));
 const hooks=new Map(),registrations=[];
 let active=['agent_tool_search','agent_tool_load','published_write'];
 const discovery=createToolDiscovery({tools,publications,admittedNames:['agent_tool_search','agent_tool_load','published_read'],initialNames:['published_write']});
 discovery.configure({on:(name,fn)=>hooks.set(name,fn),getActiveTools:()=>active,setActiveTools:names=>{active=names}});
 const session={getActiveToolNames:()=>active,setActiveToolsByName(names){active=names;registrations.push(names);this.agent.state.tools=names.map(name=>({name}));},
  agent:{state:{tools:[]},streamFunction:(_model,context)=>context.tools}};
 discovery.installSession(session);
 await assert.rejects(discovery.tools[1].execute('denied',{names:['published_write']}),/No tools were activated/);
 await discovery.tools[1].execute('allowed',{names:['published_read']});
 hooks.get('turn_end')();
 assert(registrations.every(names=>!names.includes('published_write')));
 assert.deepEqual(discovery.admittedTools.map(tool=>tool.name),['published_read']);
 const visible=session.agent.streamFunction(null,{tools:[...tools,{name:'agent_tool_load'}]});
 assert(!visible.some(tool=>tool.name==='published_write'));assert(visible.some(tool=>tool.name==='published_read'));
 discovery.close();
});
