import {spawn} from 'node:child_process';
import {createToolIdentityResolver} from './tool-identity.mjs';
let seq=0;const pending=new Map();
const request=(kind,args)=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});process.send({kind,id,...args});});
process.on('message',async message=>{
  if(message.kind==='reply'){const p=pending.get(message.id);if(p){pending.delete(message.id);message.error?p.reject(Error(message.error)):p.resolve(message.value);}return;}
  if(message.kind!=='start')return;
  const identities=createToolIdentityResolver(message.schemas);
  const saveContext=(name,spec)=>request('save',{name,spec});
  const loadContext=path=>request('load',{path});
  const tools={call:(name,args,options)=>request('call',{name:identities.resolve(name),args,options}),
    batch:async (calls,options)=>{
      const plan=await request('preflight',{calls,options});
      return Promise.all(Array.from({length:plan.count},(_,index)=>request('call',{batchRef:plan.ref,index})));
    },
    plan:(calls,options)=>request('plan',{calls,options}),
    table:spec=>request('table',{spec}),
    read:(ref,pointer,page)=>request('read',{ref,pointer,page}),
    inspect:(ref,pointer='')=>request('inspect',{ref,pointer}),
    follow:(ref,pointer)=>request('follow',{ref,pointer}),
    describe:name=>message.schemas[identities.resolve(name)],
    saveContext,loadContext,
    help:()=>({
      map:'await tools.map(items, async (item,index)=>value, {concurrency?}); returns input-ordered values. Default concurrency is this program limit. Independent chains overlap; await each dependent cursor inside its mapper. On error, stop starting new items, drain active mappers and throw; completed observation refs remain recoverable. No retry.',
      read:'await tools.read(issuedRef,pointer,{offset,limit}?) returns a selected field or an array page {items,total_items,next_offset,offset}. full_result is a literal issued reference object from an observation, never an ambient variable. Inspect first, then select bounded fields.',
      saveContext:'await tools.saveContext(name,{bindings:{key:{call:issuedRef,pointer:"/data/unit"},method:{value:"declared"},missing:{unknown:true,reason:"..."}},datasets:[{name:"rows",call:issuedRef,pointer:"/data/rows"}]}); datasets is an array, not an object. Global saveContext is the same function.',
      loadContext:'await tools.loadContext(saved.path); returns {bindings,datasets:{datasetName:{data,status,provenance,gaps}}}. Global loadContext is the same function.',
      call:'await tools.call(admittedName,arguments); returns {tool,ref,ok,status,data,value,...}. tool is the host-resolved registered name. Check ok before reading data.',
      python:'await tools.python(code,data) or python(code,data); identical private-workspace helper. Receives JSON stdin and returns stdout as text. It grants no additional tools, source access or host permissions.',
      describe:'tools.describe(admittedName) returns the exact admitted tool contract. Use its inputSchema and the returned result structure; do not guess parameter names or result fields.',
      inspect:'await tools.inspect(issuedRef,pointer="") returns structure and bounded field pointers, not data values. When needed, inspect and read selected fields in the same program.',
      follow:'await tools.follow(issuedRef,pointer); executes an unchanged action from an issued observation with grant/schema checks and returned waits. A returned source result reference is not an observation ref.',
    }),
    map:async(items,mapper,options={})=>{
      const concurrency=options?.concurrency??message.concurrency;
      if(!Array.isArray(items)||typeof mapper!=='function'||!options||typeof options!=='object'||Array.isArray(options)||
          Object.keys(options).some(key=>key!=='concurrency')||!Number.isSafeInteger(concurrency)||concurrency<1||concurrency>message.concurrency)
        throw Error('tools.map expects an array, async mapper and optional concurrency within the program limit');
      const out=new Array(items.length);let next=0,failed=false,failure;
      await Promise.all(Array.from({length:Math.min(concurrency,items.length)},async()=>{
        while(!failed&&next<items.length){
          const index=next++;
          try{out[index]=await mapper(items[index],index);}
          catch(error){if(!failed){failed=true;failure=error;}}
        }
      }));
      if(failed)throw failure;return out;
    }};
  const python=(code,data)=>new Promise((resolve,reject)=>{
    const child=spawn('python3',['-c',code],{stdio:['pipe','pipe','pipe']});let output='',error='';
    child.stdout.on('data',b=>{output+=b;if(Buffer.byteLength(output)>message.outputBytes){child.kill();reject(Error('Python output budget exceeded'));}});
    child.stderr.on('data',b=>{error=(error+b).slice(-4096);});child.on('error',reject);
    child.on('close',code=>code===0?resolve(output):reject(Error(error||`Python exited ${code}`)));
    child.stdin.on('error',()=>{});child.stdin.end(JSON.stringify(data));
  });
  tools.python=python;
  try{
    if(message.calls){
      const plan=await request('preflight',{calls:message.calls.map(({tool,arguments:args})=>({tool,arguments:args}))});
      const settled=await Promise.allSettled(message.calls.map((_,index)=>request('call',{batchRef:plan.ref,index})));
      const value=settled.map((out,index)=>({... (out.status==='fulfilled'?out.value:
        {ok:false,ref:null,status:'error',execution_status:'unknown',error:String(out.reason?.message??out.reason)}),tool:identities.resolve(message.calls[index].tool),id:message.calls[index].id,index}));
      process.send({kind:'done',value});return;
    }
    const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
    const value=await new AsyncFunction('tools','python','saveContext','loadContext','print',message.program)(tools,python,
      saveContext,loadContext,text=>request('print',{text:String(text)}));
    process.send({kind:'done',value});
  }catch(error){process.send({kind:'failed',error:String(error.message??error)});}
});
