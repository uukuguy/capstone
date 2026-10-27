import {spawn} from 'node:child_process';
let seq=0;const pending=new Map();
const request=(kind,args)=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});process.send({kind,id,...args});});
process.on('message',async message=>{
  if(message.kind==='reply'){const p=pending.get(message.id);if(p){pending.delete(message.id);message.error?p.reject(Error(message.error)):p.resolve(message.value);}return;}
  if(message.kind!=='start')return;
  const tools={call:(name,args)=>request('call',{name,args}),describe:name=>message.schemas[name]};
  const python=(code,data)=>new Promise((resolve,reject)=>{
    const child=spawn('python3',['-c',code],{stdio:['pipe','pipe','pipe']});let output='',error='';
    child.stdout.on('data',b=>{output+=b;if(Buffer.byteLength(output)>message.outputBytes){child.kill();reject(Error('Python output budget exceeded'));}});
    child.stderr.on('data',b=>{error=(error+b).slice(-4096);});child.on('error',reject);
    child.on('close',code=>code===0?resolve(output):reject(Error(error||`Python exited ${code}`)));
    child.stdin.on('error',()=>{});child.stdin.end(JSON.stringify(data));
  });
  try{
    const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
    const value=await new AsyncFunction('tools','python','saveContext','loadContext','print',message.program)(tools,python,
      (name,spec)=>request('save',{name,spec}),path=>request('load',{path}),text=>request('print',{text:String(text)}));
    process.send({kind:'done',value});
  }catch(error){process.send({kind:'failed',error:String(error.message??error)});}
});
