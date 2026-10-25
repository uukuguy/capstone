// Exercise public diagnostic correction through parent and child pinned SDK sessions.
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createManagedChildSession,applicationToolOptions,createIsolatedNativeTools} from '../../src/capstone_agent/resources/general-sdk.mjs';
import {configureDiagnosisCorrectionGuard,watchDiagnosisValidation} from '../../src/capstone_agent/resources/systematic-diagnosis.mjs';
const sdkRoot=resolve(import.meta.dirname,'../../../../.grid-agent/runtime/pi/source/packages');
const sdk=await import(pathToFileURL(resolve(sdkRoot,'coding-agent/dist/index.js')).href);
const ai=await import(pathToFileURL(resolve(sdkRoot,'ai/dist/index.js')).href);
const [root,port,mode]=process.argv.slice(2);
process.chdir(root);process.env.PI_CODING_AGENT_DIR=resolve(root,'agent');await mkdir(process.env.PI_CODING_AGENT_DIR,{recursive:true});
await writeFile('useful-output.txt','Retained facts');
const config={model:'fixed',settings:{},extensions:[],allowedSkills:[],contextFiles:[],diagnosisContextPath:port,
  applicationPolicy:{allowed_tools:['agent_diagnosis_record','agent_diagnosis_guide','write']}};
const model={id:'fixed',name:'Offline',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',
  reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
let requests=0,probeId,lastRejection;
const probeIds=[];
const begin={issue:'The selected column is absent.',input_version:'fixture',evidence_refs:[],hypothesis:'The header is amount.',
  minimal_probe:'Read the header with a permitted tool.',retry_reason:'First investigation.',comparison:'The alternate column works.',
  rejected_hypotheses:[],acceptance:'advisory'};
const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
  streamSimple(_model,context){
    const index=requests++;
    for(const message of context.messages){
      const record=message.details?.diagnosis?.record;if(record?.probe_id){probeId=record.probe_id;if(!probeIds.includes(probeId))probeIds.push(probeId);}
      if(message.details?.diagnosis?.extra_fields)lastRejection=message.details.diagnosis;
    }
    const finish={probe_id:probeId,outcome:'passed',outcome_refs:[],information_gained:'The header is amount.',
      rejected_hypotheses:[],next_disposition:'continue'};
    let args;
    let toolName='agent_diagnosis_record';
    if(index===0)args={operation:'begin',record:begin};
    else if(mode.endsWith('two-scopes')){
      if(index===1)args={operation:'begin',record:{...begin,issue:'Another independently retained probe'}};
      else if(index<=7)args={operation:'finish',record:{...finish,probe_id:probeIds[index<5?0:1],issue:'copied begin field'}};
      else if(index===8)args={issue:'Keep both unresolved probe records.',outcome:'unknown',information_gained:'Useful independent work is retained.',next_disposition:'retain_gap'};
    }
    else if(mode.endsWith('schema-separated')){
      if(index<=8){
        if(index%2)args={operation:'finish',record:[]};
        else{toolName='write';args={path:'independent-progress.txt',content:'Actual independent work '+index};}
      }
    }
    else if(mode.includes('schema'))args={operation:'finish',record:[]};
    else if(mode.endsWith('ignore'))args=index%2===0?{operation:'read'}:
      {operation:'finish',record:{...finish,issue:'changed-label-'+index}};
    else if(index===1||mode.endsWith('gap')&&index<=3)args={operation:'finish',record:{...finish,issue:'copied begin field'}};
    else if(index===2&&!mode.endsWith('gap'))args={operation:'finish',record:finish};
    else if(index===(mode.endsWith('gap')?4:3))args={issue:'The header mismatch is understood.',outcome:mode.endsWith('gap')?'unknown':'passed',
      information_gained:'Useful work is retained. The mean from the saved probe is 4.',next_disposition:'retain_gap',
      limitations:['The old reserved probe is unchanged unless its explicit finish succeeded.']};
    const content=args?[{type:'toolCall',id:'diagnosis-'+index,name:toolName,arguments:args}]:
      [{type:'text',text:'Useful work is retained with its explicit metadata gap.'}];
    const message={role:'assistant',content,api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),
      stopReason:args?'toolUse':'stop',usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{total:0}}};
    const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
  }};
let owned;
if(mode.startsWith('child'))owned=await createManagedChildSession(config,sdk,runtime,{cwd:root,toolNames:config.applicationPolicy.allowed_tools});
else{
  const settingsManager=sdk.SettingsManager.inMemory({});
  const loader=new sdk.DefaultResourceLoader({cwd:root,agentDir:process.env.PI_CODING_AGENT_DIR,settingsManager,
    noExtensions:true,noSkills:true,noPromptTemplates:true,noThemes:true,noContextFiles:true,agentsFilesOverride:()=>({agentsFiles:[]}),
    extensionFactories:[pi=>configureDiagnosisCorrectionGuard(pi,config)]});await loader.reload();
  const {session}=await sdk.createAgentSession({cwd:root,agentDir:process.env.PI_CODING_AGENT_DIR,resourceLoader:loader,
    settingsManager,modelRuntime:runtime,model,sessionManager:sdk.SessionManager.inMemory(),...applicationToolOptions(config,createIsolatedNativeTools(sdk,root))});
  await session.bindExtensions({onError:()=>{}});session.setActiveToolsByName(config.applicationPolicy.allowed_tools);
  const stop=watchDiagnosisValidation(session,config);
  owned={session,close:async()=>{stop();session.dispose();}};
}
let failure;
try{await owned.session.prompt('Retain the observed diagnosis and continue useful work.');}
catch(error){failure=error.code??error.message;}
const final=owned.session.messages.at(-1),toolResults=owned.session.messages.filter(item=>item.role==='toolResult');
await owned.close();
process.stdout.write(JSON.stringify({done:{requests,failure,stopReason:final?.stopReason,final:final?.content,lastRejection,
  errors:toolResults.filter(item=>item.isError).length,retained:await readFile('useful-output.txt','utf8')}})+'\n');
