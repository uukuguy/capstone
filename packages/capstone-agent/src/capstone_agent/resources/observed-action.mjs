// Returned actions are copied from host observations, never from model-edited
// response objects. Identity/schema/grant checks remain on the ordinary call path.
export function observedAction(records,ref,path){
  const record=records.get(ref);
  if(!record)throw Error('/ref: Unknown observation reference');
  if(record.ok!==true)throw Error('/ref: action source was not a successful observation');
  if(typeof path!=='string'||(path!==''&&!path.startsWith('/')))throw Error('/pointer: expected a JSON pointer');
  let value=record.value;
  for(const key of (path===''?[]:path.slice(1).split('/').map(k=>k.replace(/~1/g,'/').replace(/~0/g,'~')))){
    if(!value||typeof value!=='object'||!Object.hasOwn(value,key))throw Error('/pointer: observed action not found');
    value=value[key];
  }
  if(!value||typeof value!=='object'||typeof value.tool!=='string'||!value.arguments||
      typeof value.arguments!=='object'||Array.isArray(value.arguments))throw Error('/pointer: expected an observed action with tool and arguments');
  const waits=[value.not_before_seconds,record.value?.data?.poll_after_seconds].filter(v=>v!==undefined);
  if(waits.some(v=>typeof v!=='number'||!Number.isFinite(v)||v<0))throw Error('/pointer: invalid returned wait duration');
  return {name:value.tool,args:structuredClone(value.arguments),
    waitMs:Math.max(0,(record.observedAt??Date.now())+Math.max(0,...waits)*1000-Date.now())};
}
