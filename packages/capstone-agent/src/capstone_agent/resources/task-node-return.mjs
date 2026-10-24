// Model-facing semantic returns. Exact execution identity remains host-owned.
const clone=structuredClone;
const requireValue=(ok,field,detail={})=>{if(!ok){const error=new TypeError('Task return: invalid '+field);
  error.diagnostic={code:'task_return_invalid',field,...detail};throw error;}};
const exact=(value,keys)=>value&&typeof value==='object'&&!Array.isArray(value)&&
  Object.keys(value).sort().join(',')===[...keys].sort().join(',');
const text=value=>typeof value==='string'&&value.trim().length>0;
const path=value=>text(value)&&!value.includes('\\')&&!value.includes('\0')&&
  value.split('/').every(part=>part&&part!=='.'&&part!=='..'&&!part.startsWith('.'));
function selectedProducts(value){
  const products=new Map(),limitations=[];
  requireValue(Array.isArray(value?.outputs),'outputs');
  for(const item of value.outputs){
    if(!Array.isArray(item?.files))continue;
    for(const file of item.files){
      requireValue(file&&typeof file==='object'&&path(file.path),'file path');
      const selected=typeof file.role==='string'?file.role.trim().toLowerCase():undefined;
      let role=['primary','support','reproduction'].includes(selected)?selected:'support';
      if(role!==selected)limitations.push('An unspecified or unknown file role was recorded as support.');
      if(products.has(file.path)&&products.get(file.path).role!==role){
        role='support';limitations.push('Conflicting file roles were recorded as support.');
      }
      products.set(file.path,{path:file.path,role});
    }
  }
  return {products:[...products.values()],limitations:[...new Set(limitations)]};
}

export function createTaskNodeReturn(action,node,inputs){
  const binding=clone({action_id:action.id,definition_ref:action.definition_ref,execution_revision:action.execution_revision,
    consumed_results:action.input_bindings.map(item=>item.result_ref),source_versions:action.source_versions});
  const declarations=clone(node),aliases=new Map(),observed=new Map();
  const selected=inputs.manifests.filter(item=>binding.consumed_results.includes(item.result_ref));
  for(const ref of new Set(selected.flatMap(item=>item.observation_refs??[])))aliases.set('i'+(aliases.size+1),ref);
  const inherited=ref=>[...aliases].find(([,value])=>value===ref)?.[0];
  const assignment={mode:node.mode??'execute',purpose:node.purpose,instruction:node.instruction,questions:clone(node.questions),
    outputs:clone(node.outputs),checks:(node.checks??[]).map((description,index)=>({check:index+1,description})),
    inputs:selected.map(item=>({names:action.input_bindings.filter(input=>input.result_ref===item.result_ref).map(input=>input.input_name??input.name),
      summary:item.summary,scope:item.scope,input_limitations:clone([...new Map([
        ...(item.input_limitations??[]),...action.input_bindings.filter(input=>input.result_ref===item.result_ref)
          .flatMap(input=>input.accepted_limitations?[input.accepted_limitations]:[])]
        .map(limit=>[limit.result_ref+'\0'+limit.assessment_ref,limit])).values()]),
      observations:(item.observation_refs??[]).map(inherited),
      files:inputs.handles.filter(handle=>handle.result_ref===item.result_ref).map(handle=>({path:handle.path,
        kind:item.artifact_refs?.includes(handle.ref)?'product':'observation',read_only:true,
        ...Object.fromEntries(['file_name','media_type','size_bytes','sha256','roles','output_slot']
          .filter(key=>handle[key]!==undefined).map(key=>[key,clone(handle[key])]))}))})),
    return_format:{schema:'capstone-task-return/1',outputs:(node.outputs??[]).map(output=>({slot:output.slot,
      summary:'',scope:'',observations:[],files:[]})),checks:(node.checks??[]).map((_,index)=>({check:index+1,
      status:'not_run',observations:[],explanation:''})),limitations:[]}};
  const resolve=(values,location,limitations)=>{
    requireValue(Array.isArray(values),'observations');
    const admitted=new Set(aliases.values());
    const refs=values.map(alias=>{
      const ref=aliases.get(alias)??(admitted.has(alias)?alias:undefined);
      return ref;
    });
    const unverified=refs.some(ref=>ref===undefined);
    if(unverified)limitations.push(location+': unverified references were omitted; the associated findings remain producer claims.');
    return {refs:[...new Set(refs.filter(ref=>typeof ref==='string'))],unverified};
  };
  return {assignment,selectProducts(value){return selectedProducts(value).products;},
    submission(value,submissionRef){
      requireValue(text(value?.summary)&&Array.isArray(value.outputs)&&text(submissionRef),'submission');
      const supplied=new Map(),notes=[...(value.limitations??[])];
      for(const item of value.outputs){
        if(!declarations.outputs.some(output=>output.slot===item?.slot)){
          notes.push('Unbound output was retained as a producer statement; its slot was not declared.');continue;
        }
        const prior=supplied.get(item.slot);
        supplied.set(item.slot,prior?{...prior,summary:[prior.summary,item.summary].filter(text).join('\n'),
          files:[...(prior.files??[]),...(item.files??[])],observations:[...(prior.observations??[]),...(item.observations??[])]}:item);
      }
      const result={schema:'capstone-task-return/1',outputs:[...supplied.values()].map(item=>({slot:item.slot,
        summary:text(item.summary)?item.summary:value.summary,
        scope:'Producer statement for '+declarations.purpose+'; not independent analytical verification.',
        observations:item.observations?.length?item.observations:[submissionRef],files:item.files??[]})),
        checks:(value.checks??[]).map(item=>({check:item.check,status:item.status,explanation:item.explanation,
          observations:item.observations??[]})),limitations:notes};
      this.normalize(result);return result;
    },
    observe(ref){
      requireValue(text(ref),'host observation');
      if(!observed.has(ref)){const alias='o'+(observed.size+1);observed.set(ref,alias);aliases.set(alias,ref);}
      return observed.get(ref);
    },
    normalize(value){
      requireValue(exact(value,['schema','outputs','checks','limitations'])&&value.schema==='capstone-task-return/1','schema');
      requireValue(Array.isArray(value.limitations)&&value.limitations.every(text),'limitations');
      const selected=selectedProducts(value),limitations=[...clone(value.limitations),...selected.limitations];
      requireValue(Array.isArray(value.outputs)&&
        new Set(value.outputs.map(item=>item?.slot)).size===value.outputs.length,'output slots');
      const outputs=value.outputs.map((item,index)=>{
        requireValue(exact(item,['slot','summary','scope','observations','files'])&&
          declarations.outputs.some(output=>output.slot===item.slot)&&text(item.summary)&&text(item.scope),'output');
        requireValue(Array.isArray(item.files),'files');
        const product_paths=[...new Set(item.files.map(file=>file.path))];
        return {slot:item.slot,summary:item.summary,scope:item.scope,product_paths,observation_refs:resolve(item.observations,'outputs['+index+'].observations',limitations).refs};
      });
      for(const output of declarations.outputs)if(!outputs.some(item=>item.slot===output.slot))limitations.push('Missing declared output: '+output.slot+'.');
      requireValue(Array.isArray(value.checks)&&
        new Set(value.checks.map(item=>item?.check)).size===value.checks.length,'checks');
      const checks=value.checks.map((item,index)=>{
        requireValue(exact(item,['check','status','observations','explanation'])&&Number.isInteger(item.check)&&
          item.check>0&&item.check<=declarations.checks.length&&['passed','failed','not_run'].includes(item.status)&&text(item.explanation),'check');
        const {refs,unverified}=resolve(item.observations,'checks['+index+'].observations',limitations);
        const unsupported=item.status==='passed'&&(!refs.length||unverified);
        if(unsupported)limitations.push('checks['+index+']: the reported pass could not be verified from admitted references.');
        return {description:declarations.checks[item.check-1],status:unsupported?'not_run':item.status,refs,
          explanation:unsupported?'Host verification not run: insufficient admitted support. Producer reported passed: '+item.explanation:item.explanation};
      });
      declarations.checks.forEach((description,index)=>{
        if(value.checks.some(item=>item.check===index+1))return;
        checks.push({description,status:'not_run',refs:[],explanation:'The task did not return this check.'});
        limitations.push('Check not returned: '+description+'.');
      });
      return {products:selected.products,proposal:{schema:'capstone-node-proposal/1',binding:clone(binding),outputs,checks,limitations}};
    }};
}
