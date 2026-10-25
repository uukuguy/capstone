// Exercise the pinned SDK against the real Python host receipt port.
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {configureGraphParentContext,runSettledPrompt} from '../../src/capstone_agent/resources/general-sdk.mjs';

const sdkRoot=resolve(import.meta.dirname,'../../../../.grid-agent/runtime/pi/source/packages');
const sdk=await import(pathToFileURL(resolve(sdkRoot,'coding-agent/dist/index.js')).href);
const ai=await import(pathToFileURL(resolve(sdkRoot,'ai/dist/index.js')).href);
const [root,port,mode,numeric]=process.argv.slice(2);
process.chdir(root);process.env.PI_CODING_AGENT_DIR=resolve(root,'agent');await mkdir(process.env.PI_CODING_AGENT_DIR,{recursive:true});
await writeFile('useful-output.txt','Retained facts');
const model={id:'fixed',name:'Offline',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',
  reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
let requests=0,failedExecutions=0,independentExecutions=0,guard;
const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
  streamSimple(_model,context){
    const index=requests++;
    const bad=mode==='recovery'?index===0:index<6||mode==='independent'&&index===6||mode==='ignore';
    const good=mode==='independent'&&index===7;
    const content=bad||good?[{type:'toolCall',id:'call-'+index,name:'fixture_read',arguments:{path:good?'retained':'missing',
      ...(numeric===undefined?{}:{factor:JSON.parse(numeric)})}}]:
      [{type:'text',text:'Useful work is retained. The missing input remains an explicit gap.'}];
    const message={role:'assistant',content,api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),
      stopReason:bad||good?'toolUse':'stop',usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{total:0}}};
    const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
  }};
const settingsManager=sdk.SettingsManager.inMemory({});
const controller={readParentInputs:async()=>null,progressKey:async()=>String(independentExecutions)};
const config={diagnosisContextPath:port,applicationPolicy:{allowed_tools:['agent_diagnosis_record']},
  researchRuntime:{graphSchema:'capstone-enterprise-graph/2'}};
const loader=new sdk.DefaultResourceLoader({cwd:root,agentDir:process.env.PI_CODING_AGENT_DIR,settingsManager,
  noExtensions:true,noSkills:true,noPromptTemplates:true,noThemes:true,noContextFiles:true,agentsFilesOverride:()=>({agentsFiles:[]}),
  extensionFactories:[pi=>{
    guard=configureGraphParentContext(pi,config,controller);
    pi.registerTool({name:'fixture_read',description:'Read a selected fixture input.',
      parameters:{type:'object',properties:{path:{type:'string'},factor:{type:'number'}},required:['path'],additionalProperties:false},
      execute:async(_id,args)=>{
        if(args.path==='retained'){independentExecutions++;return {content:[{type:'text',text:'Independent useful result'}]};}
        failedExecutions++;return {isError:true,content:[{type:'text',text:'The selected input is missing.'}],
          details:{ok:false,error:{category:'rejected',code:'source_unavailable'}}};
      }});
  }]});
await loader.reload();
const {session}=await sdk.createAgentSession({cwd:root,agentDir:process.env.PI_CODING_AGENT_DIR,resourceLoader:loader,
  settingsManager,modelRuntime:runtime,model,sessionManager:sdk.SessionManager.inMemory()});
let failure;
try{
  await session.bindExtensions({onError:()=>{}});session.setActiveToolsByName(['fixture_read']);
  await runSettledPrompt(session,{kind:'text',text:'Read the input. Keep useful work if it remains unavailable.'},null,()=>{},undefined,
    {failure:()=>guard.failure()});
}catch(error){failure=error.code??error.message;}
finally{session.dispose();}
process.stdout.write(JSON.stringify({done:{requests,failedExecutions,independentExecutions,failure,
  final:session.messages.at(-1)?.content,retained:await readFile('useful-output.txt','utf8')}})+'\n');
