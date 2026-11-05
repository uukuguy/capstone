import {spawn} from 'node:child_process';
import {createToolIdentityResolver} from './tool-identity.mjs';
let seq=0;const pending=new Map();
const request=(kind,args)=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});process.send({kind,id,...args});});
process.on('message',async message=>{
  if(message.kind==='reply'){const p=pending.get(message.id);if(p){pending.delete(message.id);message.error?p.reject(Error(message.error)):p.resolve(message.value);}return;}
  if(message.kind!=='start')return;
  const identities=createToolIdentityResolver(message.schemas);
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
    describe:name=>message.schemas[identities.resolve(name)]};
  const python=(code,data)=>new Promise((resolve,reject)=>{
    const child=spawn('python3',['-c',code],{stdio:['pipe','pipe','pipe']});let output='',error='';
    child.stdout.on('data',b=>{output+=b;if(Buffer.byteLength(output)>message.outputBytes){child.kill();reject(Error('Python output budget exceeded'));}});
    child.stderr.on('data',b=>{error=(error+b).slice(-4096);});child.on('error',reject);
    child.on('close',code=>code===0?resolve(output):reject(Error(error||`Python exited ${code}`)));
    child.stdin.on('error',()=>{});child.stdin.end(JSON.stringify(data));
  });
  try{
    if(message.calls){
      const plan=await request('preflight',{calls:message.calls.map(({tool,arguments:args})=>({tool,arguments:args}))});
      const settled=await Promise.allSettled(message.calls.map((_,index)=>request('call',{batchRef:plan.ref,index})));
      const value=settled.map((out,index)=>({... (out.status==='fulfilled'?out.value:
        {ok:false,ref:null,status:'error',execution_status:'unknown',error:String(out.reason?.message??out.reason)}),id:message.calls[index].id,index}));
      process.send({kind:'done',value});return;
    }
    const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
    const value=await new AsyncFunction('tools','python','saveContext','loadContext','print',message.program)(tools,python,
      (name,spec)=>request('save',{name,spec}),path=>request('load',{path}),text=>request('print',{text:String(text)}));
    process.send({kind:'done',value});
  }catch(error){process.send({kind:'failed',error:String(error.message??error)});}
});
