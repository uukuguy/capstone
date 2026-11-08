import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';

// The caller supplies only task-admitted native resources, never model paths.
export function createSkillRecordTool(skills){
  const admitted=new Map(skills.map(skill=>[skill.name,{...skill,
    version:'sha256:'+createHash('sha256').update(readFileSync(skill.filePath)).digest('hex')}]));
  const loaded=new Set();
  const fail=code=>({isError:true,content:[{type:'text',text:code}]});
  return {name:'agent_skill',label:'Use task skill',
    description:'Load an admitted skill by exact name, or report a meaningful public application phase after loading. Loading returns the method. Reports are model statements, not host verification. refs and tool_call_ids link reported work; they do not grant authority. Do not report private reasoning. Available skills: '+skills.map(s=>s.name+': '+s.description).join('; '),
    parameters:{type:'object',additionalProperties:false,required:['name','operation'],properties:{
      name:{type:'string',minLength:1,maxLength:128},operation:{type:'string',enum:['load','report']},
      phase:{type:'string',maxLength:80},summary:{type:'string',minLength:1,maxLength:600},
      refs:{type:'array',maxItems:32,items:{type:'string',minLength:1,maxLength:256}},
      tool_call_ids:{type:'array',maxItems:32,items:{type:'string',minLength:1,maxLength:256}}}},
    async execute(id,args,signal){
      signal?.throwIfAborted();
      if(!args||Object.keys(args).some(key=>!['name','operation','phase','summary','refs','tool_call_ids'].includes(key)))return fail('skill_arguments_invalid');
      const skill=admitted.get(args.name);
      if(!skill)return fail('skill_not_admitted');
      if(!['load','report'].includes(args.operation))return fail('skill_operation_invalid');
      if(args.phase!==undefined&&(typeof args.phase!=='string'||args.phase.length>80))return fail('skill_arguments_invalid');
      for(const key of ['refs','tool_call_ids'])if(args[key]!==undefined&&(!Array.isArray(args[key])||args[key].length>32||args[key].some(v=>typeof v!=='string'||!v||v.length>256)))return fail('skill_arguments_invalid');
      let body;
      try{body=readFileSync(skill.filePath);}catch{return fail('skill_unavailable');}
      if('sha256:'+createHash('sha256').update(body).digest('hex')!==skill.version)return fail('skill_version_changed');
      if(body.length>65536)return fail('skill_content_too_large');
      if(args.operation==='report'&&(!loaded.has(skill.name)||typeof args.summary!=='string'||!args.summary.trim()||args.summary.length>600))return fail('skill_report_requires_load_and_summary');
      if(args.operation==='load')loaded.add(skill.name);
      const activity={schema:'capstone-skill-activity/1',name:skill.name,version:skill.version,
        state:args.operation==='load'?'loaded':'reported',source:args.operation==='load'?'host':'model',
        ...(args.operation==='report'?{summary:args.summary,phase:args.phase??'application',
          refs:args.refs??[],tool_call_ids:args.tool_call_ids??[]}: {})};
      return {content:[{type:'text',text:args.operation==='load'?body.toString('utf8'):JSON.stringify(activity)}],
        details:{skill_activity:activity}};
    }};
}
