import {assertCapacity} from './applicationCapacity'

export type SessionSkill={id:string;version:string;role:'delegated_pi'|'direct_pi';loaded_identity?:string;native_name?:string;catalog_revision?:string}
export type SessionSkills={revision:number;skills:SessionSkill[]}
export function parseSessionSkills(value:unknown):SessionSkills{
  if(value===undefined||value===null)return {revision:0,skills:[]}
  const item=value as SessionSkills
  if(typeof item!=='object'||Array.isArray(item)||Object.keys(item).sort().join(',')!=='revision,skills'||!Number.isSafeInteger(item.revision)||item.revision<0||!Array.isArray(item.skills))throw new Error('会话技能配置无效')
  assertCapacity(item.skills.length,'context_references')
  const seen=new Set<string>()
  for(const skill of item.skills){
    if(!skill||typeof skill!=='object'||!['id','role','version'].every(key=>Object.hasOwn(skill,key))||Object.keys(skill).some(key=>!['id','role','version','loaded_identity','native_name','catalog_revision'].includes(key))||!['delegated_pi','direct_pi'].includes(skill.role)||Object.values(skill).some(v=>typeof v!=='string'||!v.trim()||v.length>256)||seen.has(skill.id))throw new Error('会话技能配置无效')
    seen.add(skill.id)
  }
  return {revision:item.revision,skills:item.skills.map(skill=>({...skill}))}
}
