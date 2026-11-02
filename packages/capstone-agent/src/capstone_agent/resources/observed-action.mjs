// Returned actions are copied from host observations, never from model-edited
// response objects. Identity/schema/grant checks remain on the ordinary call path.
export class ObservationPointerError extends Error {}
export function observationPointer(value,path=''){
  if(typeof path!=='string'||(path!==''&&!path.startsWith('/')))throw Error('/pointer: expected a JSON pointer; use empty string for the root');
  let parent='';
  for(const encoded of (path===''?[]:path.slice(1).split('/'))){
    const key=encoded.replace(/~1/g,'/').replace(/~0/g,'~');
    if(value===null||typeof value!=='object'||!Object.hasOwn(value,key)){
      const keys=value&&typeof value==='object'?Object.keys(value):[];
      throw new ObservationPointerError('/pointer: source field missing; '+JSON.stringify({
        pointer:path.slice(0,256),parent_pointer:parent.slice(0,256),
        parent_type:value===null?'null':Array.isArray(value)?'array':typeof value,
        available_keys:keys.slice(0,16).map(k=>k.slice(0,80)),keys_truncated:keys.length>16,
      })+'; tools.read returns the selected field directly, without a value wrapper. Read an existing field from the same reference; do not repeat the upstream call');
    }
    value=value[key];parent+='/'+encoded;
  }
  return value;
}
export function observationRecordPointer(record,path=''){
  const prefix=record.envelope_pointer;
  if(prefix&&typeof path==='string'&&(path===prefix||path.startsWith(prefix+'/')))path=path.slice(prefix.length);
  return observationPointer(record.value,path);
}
export function readObservation(records,ref,path){
  const record=records.get(ref);
  if(!record)throw Error('/ref: Unknown observation reference; use an exact task-issued observation_ref, tools.call/completed_calls ref or full_result object. Call/source identifiers work only when issued and retained by this task; do not reconstruct them or use another task\'s references.');
  return structuredClone(observationRecordPointer(record,path));
}
export function observedAction(records,ref,path){
  const record=records.get(ref);
  if(!record)throw Error('/ref: Unknown observation reference');
  if(record.ok!==true)throw Error('/ref: action source was not a successful observation');
  const value=readObservation(records,ref,path);
  if(!value||typeof value!=='object'||typeof value.tool!=='string'||!value.arguments||
      typeof value.arguments!=='object'||Array.isArray(value.arguments))throw Error('/pointer: expected an observed action with tool and arguments');
  const source=record.value?.structuredContent??record.value;
  const waits=[value.not_before_seconds,source?.data?.poll_after_seconds].filter(v=>v!==undefined);
  if(waits.some(v=>typeof v!=='number'||!Number.isFinite(v)||v<0))throw Error('/pointer: invalid returned wait duration');
  return {name:value.tool,args:structuredClone(value.arguments),
    waitMs:Math.max(0,(record.observedAt??Date.now())+Math.max(0,...waits)*1000-Date.now())};
}
