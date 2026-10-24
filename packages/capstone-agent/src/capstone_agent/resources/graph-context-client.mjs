import {createHash} from 'node:crypto';
import {open} from 'node:fs/promises';
import {constants} from 'node:fs';
import {join,isAbsolute} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {checkCapacity,runtimeLimits} from './runtime-limits.mjs';

const SCHEMA='capstone-enterprise-graph-context/1';
function canonical(value){
  if(Array.isArray(value))return value.map(canonical);
  return value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
}
const digest=value=>createHash('sha256').update(JSON.stringify(canonical(value))).digest('hex');
export class GraphContextError extends Error {
  constructor(category,request_id,operation,rejection_code,lease){
    super(category==='rejected'?'Host rejected the graph context selection. Correct the selection; replaying this saved rejection cannot change its outcome.':
      'Graph context receipt identity or persistence is not confirmed. Recover the exact request before repeating native work.');
    this.name='GraphContextError';this.category=category;this.code='graph_context_'+category;
    this.request_id=request_id;this.operation=operation;
    if(rejection_code)this.rejection_code=rejection_code;
    if(lease){this.action_id=lease.action_id;this.checkpoint=structuredClone(lease.checkpoint);}
  }
}

// Only host receipts can return sealed handles. This port is never a model tool.
export function createGraphContextClient(config,{emit=frame=>process.stdout.write(JSON.stringify(frame)+'\n')}={}){
  if(typeof config.graphContextPath!=='string'||!isAbsolute(config.graphContextPath))throw new TypeError('Host graph context path is required');
  const capacities=runtimeLimits(config.runtimeLimits,{mode:config.runtimeLimitMode}),confirmed=new Map(),sent=new Map();
  async function request(operation,{action,checkpoint,selection},{signal,requestKey}={}){
    signal?.throwIfAborted();
    if(!action?.id||!checkpoint?.ref||!Number.isSafeInteger(checkpoint.revision))throw new TypeError('An exact committed graph lease is required');
    const payload={type:'enterprise_graph_context_request',schema:SCHEMA,owner:config.researchOwner,
      attempt_id:config.researchAttemptId,task_id:config.researchTaskId,action_id:action.id,checkpoint,operation,selection};
    if(requestKey!==undefined&&(typeof requestKey!=='string'||!/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$/.test(requestKey)))
      throw new TypeError('Graph context request key is invalid');
    // A new explicit model call may retry a rejected selection. Replaying the
    // same call keeps one request identity and must never change its bytes.
    const identity=requestKey===undefined?payload:{owner:payload.owner,attempt_id:payload.attempt_id,task_id:payload.task_id,
      action_id:payload.action_id,operation,request_key:requestKey};
    const frame=structuredClone({...payload,request_id:'ctx-'+digest(identity)}),hash=digest(frame),id=frame.request_id;
    checkCapacity(capacities,'research_request_bytes',Buffer.byteLength(JSON.stringify(frame)+'\n'),'bytes','graph_context');
    if(sent.has(id)&&sent.get(id)!==hash)throw new Error('Graph context request identity changed');
    if(confirmed.has(id))return structuredClone(confirmed.get(id));
    try{
      if(!sent.has(id)){sent.set(id,hash);await emit(frame);}
      while(true){
      signal?.throwIfAborted();
      if(config.deadlineAt&&Date.now()>=config.deadlineAt)throw new DOMException('Graph context receipt deadline exceeded','TimeoutError');
      let file;
      try{
        file=await open(join(config.graphContextPath,'responses',id+'.json'),constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);
        const before=await file.stat();
        if(!before.isFile())throw new Error('Graph context receipt identity is invalid');
        checkCapacity(capacities,'research_response_bytes',before.size,'bytes','graph_context');
        const raw=await file.readFile('utf8');
        checkCapacity(capacities,'research_response_bytes',Buffer.byteLength(raw),'bytes','graph_context');
        const receipt=JSON.parse(raw);
        if(receipt.schema!==SCHEMA||receipt.request_id!==id||receipt.request_sha256!==hash)throw new Error('Graph context receipt identity changed');
        if(receipt.ok!==true)throw new GraphContextError('rejected',id,operation,
          ['selection_invalid','action_unavailable','owner_invalid','source_unavailable','capacity_exceeded'].includes(receipt.code)?receipt.code:
            receipt.code===undefined||receipt.code===null||receipt.code===''?'selection_invalid':'host_rejected',
          {action_id:action.id,checkpoint});
        confirmed.set(id,structuredClone(receipt.result));return structuredClone(receipt.result);
      }catch(error){if(error.code!=='ENOENT')throw error;}
      finally{await file?.close();}
      await delay(10,undefined,{signal});
      }
    }catch(error){
      if(error instanceof GraphContextError)throw error;
      if(error.name==='AbortError'||error.name==='TimeoutError'){
        error.request_id=id;error.operation=operation;error.category='unknown';throw error;
      }
      if(error.code==='capacity_exceeded')throw error;
      throw new GraphContextError('unknown',id,operation,undefined,{action_id:action.id,checkpoint});
    }
  }
  return Object.freeze({freeze:(args,control)=>request('freeze',args,control),resolve:(args,control)=>request('resolve',args,control),
    read:(args,control)=>request('read',args,control)});
}
