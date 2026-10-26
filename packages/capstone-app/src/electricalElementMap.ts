import type {ElectricalViewReady} from './electricalModelView'

export type NativeElementKey=string|number
export type ElectricalElementEndpoint={role:string;element_table:string;element_key:NativeElementKey;element_ref:string;source_port_refs:string[];source_port_mapping_status:'mapped'|'unavailable_or_ambiguous';[key:string]:unknown}
export type ElectricalElement={element_ref:string;element_table:string;element_key:NativeElementKey;kind:string;label:string;source_refs:string[];origin:'source'|'source_equivalence'|'source_transformation'|'scenario_created'|'transformation_internal';endpoints:ElectricalElementEndpoint[];mapping_status:'mapped'|'source_mapping_missing';scenario_object_id:string|null;endpoint_role_basis:string;[key:string]:unknown}
export type ElectricalElementMap={schema:'gateway-element-map/1';model_ref:string;model_revision:string;source_snapshot_ref:string;selection_ref:string;artifact_ref:string;engine:string;engine_version:string;scenario_revision:string;mapping_rule_version:string;mapped_elements:number;native_key_coverage_complete:boolean;covered_element_tables:string[];source_mapping_missing:number;elements:ElectricalElement[];[key:string]:unknown}
/** Produced from an application-admitted Authority result, never from an LLM claim. */
export type ElectricalResultValue={element_table:string;element_key:NativeElementKey;element_ref?:string;metric:string;value:number|null;unit:string;status?:'calculated'|'not_calculated'|'omitted'|'invalid'}
export type ElectricalResultBatch={model_ref:string;model_revision:string;artifact_ref:string;engine:string;engine_version:string;scenario_revision:string;authority_ref:string;run_ref:string;solver_status:'converged'|'not_converged'|'failed'|'unknown';rows:ElectricalResultValue[]}
export type ElectricalResultMatch={result:ElectricalResultValue;status:'bound'|'missing'|'ambiguous'|'source_mapping_missing'|'not_calculated'|'omitted'|'invalid';element?:ElectricalElement;reason?:string}
export type ElectricalResultBinding={status:'bound';authority_ref:string;run_ref:string;demo_only:boolean;matches:ElectricalResultMatch[]}|{status:'blocked';reason:'model_identity_mismatch'|'view_identity_mismatch'|'missing_authority_identity'|'solver_not_converged';matches:[]}
export class ElectricalElementMapError extends Error {constructor(public readonly code:string){super(`元素映射无效：${code}`);this.name='ElectricalElementMapError'}}
function fail(code:string):never {throw new ElectricalElementMapError(code)}
const object=(value:unknown):Record<string,unknown>=>value!==null&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:fail('object_required')
const string=(value:unknown):value is string=>typeof value==='string'&&value.length>0
const strings=(value:unknown):value is string[]=>Array.isArray(value)&&value.every(string)
const key=(value:unknown):value is NativeElementKey=>typeof value==='string'||typeof value==='number'&&Number.isSafeInteger(value)
const count=(value:unknown):value is number=>typeof value==='number'&&Number.isSafeInteger(value)&&value>=0
/** No coercion: table=line/key=7 and table=line/key="7" are different elements. */
export function nativeElementIdentity(table:string,elementKey:NativeElementKey):string {return JSON.stringify([table,typeof elementKey,elementKey])}

export function parseElectricalElementMap(value:unknown,options:{maxElements?:number}={}):ElectricalElementMap {
  const row=object(value)
  if(row.schema!=='gateway-element-map/1'||row.mapping_rule_version!=='gateway-element-map/1')fail('schema_mismatch')
  for(const field of ['model_ref','model_revision','source_snapshot_ref','selection_ref','artifact_ref','engine','engine_version','scenario_revision'])if(!string(row[field]))fail(`invalid_${field}`)
  const maxElements=options.maxElements??100000
  if(!count(maxElements)||!Array.isArray(row.elements)||row.elements.length>maxElements)fail('mapping_budget_exceeded')
  if(!count(row.mapped_elements)||row.mapped_elements!==row.elements.length||typeof row.native_key_coverage_complete!=='boolean'||!count(row.source_mapping_missing)||!strings(row.covered_element_tables)||new Set(row.covered_element_tables).size!==row.covered_element_tables.length)fail('invalid_mapping_counts')
  const byRef=new Map<string,ElectricalElement>(),byKey=new Set<string>();let missing=0
  for(const value of row.elements){
    const element=object(value)
    for(const field of ['element_ref','element_table','kind','endpoint_role_basis'])if(!string(element[field]))fail(`invalid_${field}`)
    if(!key(element.element_key)||typeof element.label!=='string'||!strings(element.source_refs)||!Array.isArray(element.endpoints)||!['source','source_equivalence','source_transformation','scenario_created','transformation_internal'].includes(String(element.origin))||!['mapped','source_mapping_missing'].includes(String(element.mapping_status))||!(element.scenario_object_id===null||string(element.scenario_object_id)))fail('invalid_element')
    if(element.origin==='scenario_created'&&!string(element.scenario_object_id))fail('missing_scenario_identity')
    const hasMapping=element.source_refs.length>0||element.origin==='scenario_created'||element.origin==='transformation_internal'
    if((element.mapping_status==='mapped')!==hasMapping)fail('inconsistent_source_mapping')
    if(!row.covered_element_tables.includes(element.element_table as string))fail('uncovered_element_table')
    if(element.mapping_status==='source_mapping_missing')missing++
    const identity=nativeElementIdentity(element.element_table as string,element.element_key)
    if(byKey.has(identity))fail('ambiguous_native_key');byKey.add(identity)
    if(byRef.has(element.element_ref as string))fail('ambiguous_element_ref');byRef.set(element.element_ref as string,element as ElectricalElement)
    for(const value of element.endpoints){const endpoint=object(value)
      if(!string(endpoint.role)||!string(endpoint.element_ref)||!string(endpoint.element_table)||!key(endpoint.element_key)||!strings(endpoint.source_port_refs)||!['mapped','unavailable_or_ambiguous'].includes(String(endpoint.source_port_mapping_status)))fail('invalid_endpoint')
      if(endpoint.source_port_mapping_status==='mapped'&&!endpoint.source_port_refs.length||endpoint.source_port_mapping_status==='unavailable_or_ambiguous'&&endpoint.source_port_refs.length)fail('inconsistent_port_mapping')
    }
  }
  if(missing!==row.source_mapping_missing)fail('invalid_missing_count')
  for(const element of byRef.values())for(const endpoint of element.endpoints){
    const target=byRef.get(endpoint.element_ref)
    if(!target||target.kind!=='bus'||target.element_table!==endpoint.element_table||target.element_key!==endpoint.element_key||typeof target.element_key!==typeof endpoint.element_key)fail('endpoint_identity_mismatch')
  }
  return row as ElectricalElementMap
}

/** Binds supplied values only to exact native elements in the selected artifact. */
export function bindElectricalResults(mapping:ElectricalElementMap,batch:ElectricalResultBatch,view:ElectricalViewReady):ElectricalResultBinding {
  const map=parseElectricalElementMap(mapping)
  if(!string(batch.authority_ref)||!string(batch.run_ref))return {status:'blocked',reason:'missing_authority_identity',matches:[]}
  for(const field of ['model_ref','model_revision','artifact_ref','engine','engine_version','scenario_revision'] as const)if(batch[field]!==map[field])return {status:'blocked',reason:'model_identity_mismatch',matches:[]}
  if(view.state!=='ready'||view.representation!=='calculation_bus_branch'||view.model_ref!==map.model_ref||view.model_revision!==map.model_revision||view.artifact_ref!==map.artifact_ref||view.source_snapshot_ref!==map.source_snapshot_ref||view.selection_ref!==map.selection_ref)return {status:'blocked',reason:'view_identity_mismatch',matches:[]}
  const derivation=view.derivation&&typeof view.derivation==='object'&&!Array.isArray(view.derivation)?view.derivation as Record<string,unknown>:undefined
  if(!derivation||typeof derivation.demo_only!=='boolean'||['artifact_ref','engine','engine_version','scenario_revision'].some(field=>derivation[field]!==map[field]))return {status:'blocked',reason:'view_identity_mismatch',matches:[]}
  if(batch.solver_status!=='converged')return {status:'blocked',reason:'solver_not_converged',matches:[]}
  if(!Array.isArray(batch.rows)||batch.rows.length>100000)fail('result_budget_exceeded')
  const index=new Map(map.elements.map(element=>[nativeElementIdentity(element.element_table,element.element_key),element])),refs=new Map(map.elements.map(element=>[element.element_ref,element])),counts=new Map<string,number>()
  for(const result of batch.rows){if(!result||typeof result!=='object')fail('invalid_result_record');if(!string(result.element_table)||!key(result.element_key)||!string(result.metric))continue;const id=JSON.stringify([nativeElementIdentity(result.element_table,result.element_key),result.metric]);counts.set(id,(counts.get(id)||0)+1)}
  const matches:ElectricalResultMatch[]=batch.rows.map(result=>{
    if(!string(result.element_table)||!key(result.element_key)||!string(result.metric)||!string(result.unit)||!['calculated','not_calculated','omitted','invalid',undefined].includes(result.status))return {result,status:'invalid',reason:'invalid_result_record'}
    const identity=nativeElementIdentity(result.element_table,result.element_key),element=index.get(identity)
    if(counts.get(JSON.stringify([identity,result.metric]))!>1)return {result,status:'ambiguous',reason:'duplicate_result_identity'}
    if(!element)return result.element_ref&&refs.has(result.element_ref)?{result,status:'ambiguous',reason:'element_ref_key_conflict'}:{result,status:'missing',reason:'native_element_not_mapped'}
    if(result.element_ref!==undefined&&result.element_ref!==element.element_ref)return {result,status:'ambiguous',reason:'element_ref_key_conflict'}
    if(result.status==='invalid'||result.value!==null&&!(typeof result.value==='number'&&Number.isFinite(result.value)))return {result,status:'invalid',element,reason:'invalid_result_value'}
    if(result.status==='omitted')return {result,status:'omitted',element}
    if(result.status==='not_calculated'||result.value===null)return {result,status:'not_calculated',element}
    if(element.mapping_status==='source_mapping_missing')return {result,status:'source_mapping_missing',element,reason:'native_identity_known_source_mapping_missing'}
    return {result,status:'bound',element}
  })
  return {status:'bound',authority_ref:batch.authority_ref,run_ref:batch.run_ref,demo_only:derivation.demo_only===true,matches}
}
