// Offline SDK conformance: scripted provider, actual SDK and native tools.
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {createInterface} from 'node:readline';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createManagedChildSession} from '../../src/capstone_agent/resources/general-sdk.mjs';
import {createTaskNodeReturn} from '../../src/capstone_agent/resources/task-node-return.mjs';

const lines=createInterface({input:process.stdin});
const setup=await new Promise(done=>lines.once('line',line=>done(JSON.parse(line))));lines.close();
const sdkRoot=resolve('.grid-agent/runtime/pi/source/packages');
const sdk=await import(pathToFileURL(join(sdkRoot,'coding-agent/dist/index.js')).href);
const ai=await import(pathToFileURL(join(sdkRoot,'ai/dist/index.js')).href);
process.chdir(setup.workspace);process.env.PI_CODING_AGENT_DIR=join(setup.workspace,'.pi');
const cwd=join(setup.workspace,'node');await mkdir(cwd);await mkdir(process.env.PI_CODING_AGENT_DIR);
const owner={thread_id:'thread',work_id:'work',research_id:'research',goal_revision:1};
const action={id:'action-A',step_id:'A',owner,attempt_id:'attempt',definition_ref:'definition-A',execution_revision:1,
  input_bindings:[],source_refs:[],source_versions:[]};
const node={purpose:'Save a useful statement',instruction:'Save the assigned statement and disclose unperformed review',questions:['What was saved?'],
  outputs:[{slot:'file',kind:'artifact',description:'Saved statement'},{slot:'finding',kind:'observation',description:'Producer finding'}],checks:['Optional analytical review']};
const adapter=createTaskNodeReturn(action,node,{manifests:[],handles:[]}),receipts=[],events=[];
const config={researchTaskId:'task',model:'offline-return',extensions:[],allowedSkills:[],contextFiles:[],
  settings:{compaction:{enabled:false},packages:[],extensions:[],skills:[]},
  applicationPolicy:{allowed_tools:[setup.cohesive?'bash':'write']},researchRuntime:{lightweightTaskNodes:true}};
const model={id:config.model,name:'Offline',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',reasoning:false,
  input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
const summary='保留 "引号" 和换行\nA useful statement; review remains open.';let turns=0;
if(setup.cohesive)await writeFile(join(cwd,'source.json'),JSON.stringify({summary}));
const program=`python3 - <<'PY'
import json, subprocess, sys
from pathlib import Path
source=json.loads(Path('source.json').read_text())
Path('worker.py').write_text('import json\\nfrom pathlib import Path\\ns=json.loads(Path("source.json").read_text())["summary"]\\nPath("result.json").write_text(json.dumps({"summary":s,"chars":len(s)}))\\n')
subprocess.run([sys.executable,'worker.py'],check=True)
result=json.loads(Path('result.json').read_text())
Path('说明.md').write_text(result['summary'])
print(json.dumps({'saved':'说明.md','chars':result['chars']}))
PY`;
const files=[{path:'说明.md',role:'primary'},...(setup.batch?[{path:'support.md',role:'support'}]:[])];
const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
  streamSimple(){
    const turn=turns++,calls=turn===0?setup.cohesive?[{name:'bash',arguments:{command:program}}]:[...files.map(file=>({name:'write',arguments:{path:file.path,content:summary}})),
      ...(setup.invalid?[{name:'write',arguments:{path:'rejected.md'}}]:[])]:turn===1?
      [{name:'agent_task_return',arguments:{summary,outputs:[{slot:'file',files,...(setup.annotations?{
        kind:'artifact',scope:'Untrusted caller scope',observation_refs:['foreign-ref'],binding:{action_id:'foreign-action'}}:{})},{slot:'finding'}],
        limitations:['Analytical review was not performed']}}]:[];
    const message={role:'assistant',content:calls.length?calls.map((call,index)=>({type:'toolCall',id:'call-'+turn+'-'+index,...call})):[{type:'text',text:'Saved with the stated limitation.'}],
      stopReason:calls.length?'toolUse':'stop',api:model.api,provider:model.provider,model:model.id,timestamp:0,
      usage:{input:2,output:3,totalTokens:5,cost:{total:0}}};
    const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
  }};
const child=await createManagedChildSession(config,sdk,runtime,{cwd,toolNames:[setup.cohesive?'bash':'write'],researchExecution:true,
  graphBinding:{action,checkpoint:{ref:'checkpoint',revision:1},emit:event=>events.push(event),receipts,taskReturn:adapter}});
try{
  assert.match(child.session.systemPrompt,/multiple tool calls in one model response/);
  assert.deepEqual(child.session.getActiveToolNames().sort(),['agent_task_return',setup.cohesive?'bash':'write']);
  await child.session.prompt('Save the statement and return it through agent_task_return.');
  assert.equal(turns,3);assert.equal(receipts.length,files.length+1+Number(!!setup.invalid));
  assert.equal(receipts.filter(item=>item.status==='failed').length,Number(!!setup.invalid));
  if(setup.invalid)await assert.rejects(readFile(join(cwd,'rejected.md')),{code:'ENOENT'});
  const saved=JSON.parse(await readFile(join(cwd,'.capstone-products.json'),'utf8')),result=adapter.normalize(saved);
  assert.equal(saved.outputs[0].summary,summary);assert.equal(await readFile(join(cwd,'说明.md'),'utf8'),summary);
  if(setup.annotations){
    assert.match(saved.outputs[0].scope,/^Producer statement for /);
    assert.equal(saved.outputs[0].binding,undefined);assert.equal(saved.outputs[0].kind,undefined);
    assert.ok(!JSON.stringify(result).includes('foreign-action'));assert.ok(!JSON.stringify(result).includes('foreign-ref'));
  }
  assert.deepEqual(result.products,files);
  for(const file of files)assert.equal(await readFile(join(cwd,file.path),'utf8'),summary);
  if(setup.cohesive){
    assert.match(child.session.systemPrompt,/Data dependencies alone do not require another model response/);
    assert.equal(JSON.parse(await readFile(join(cwd,'result.json'),'utf8')).summary,summary);
    assert.ok(await readFile(join(cwd,'worker.py'),'utf8'));
  }
  assert.deepEqual(result.proposal.outputs.map(output=>output.observation_refs),[[receipts.at(-1).ref],[receipts.at(-1).ref]]);
  assert.equal(result.proposal.checks[0].status,'not_run');
  assert.equal(events.filter(event=>event.type==='enterprise_graph_child_tool'&&event.activity==='end').length,files.length+1+Number(!!setup.invalid));
  if(setup.invalid){
    const failed=events.find(event=>event.type==='enterprise_graph_child_tool'&&event.is_error);
    assert.equal(failed.activity,'end');assert.equal(failed.execution_ms,undefined);
    assert.ok(events.some(event=>event.type==='enterprise_graph_tool_binding'&&event.tool_call_id===failed.tool_call_id));
  }
  process.stdout.write(JSON.stringify({turns,native_calls:receipts.length,structured_return:true,checks:'not_run'})+'\n');
}finally{await child.close();}
