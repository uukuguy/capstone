import {describe,it,expect} from 'vitest'
import {parseElectricalElementMap,bindElectricalResults,nativeElementIdentity,type ElectricalElement,type ElectricalElementMap,type ElectricalResultBatch} from './electricalElementMap'
import {electricalManifest} from './electricalModelFixtures'

function fixture(){
  const element=(table:string,key:number|string,ref:string,kind='bus'):ElectricalElement=>({element_ref:ref,element_table:table,element_key:key,kind,label:'Name is not an index',source_refs:[`source:${ref}`],origin:'source',endpoints:[],mapping_status:'mapped',scenario_object_id:null,endpoint_role_basis:'native_artifact_not_verified_source_terminal_role'})
  const buses=[element('bus',7,'bus-seven'),element('bus',29,'bus-twenty-nine')]
  buses[0].origin='source_equivalence';buses[0].source_refs=['source:a','source:b']
  const line=element('line',45,'line-native','line');line.label='7'
  line.endpoints=buses.map((bus,i)=>({role:i?'to':'from',element_table:bus.element_table,element_key:bus.element_key,element_ref:bus.element_ref,source_port_refs:[],source_port_mapping_status:'unavailable_or_ambiguous'}))
  const stringLine=element('line','45','line-string','line'),load=element('load',19,'load-scenario','load');load.origin='scenario_created';load.scenario_object_id='scenario-load';load.source_refs=[]
  const missing=element('trafo',2,'missing-transformer','transformer');missing.source_refs=[];missing.mapping_status='source_mapping_missing'
  const map:ElectricalElementMap={schema:'gateway-element-map/1',mapping_rule_version:'gateway-element-map/1',model_ref:'model:one',model_revision:'revision:1',source_snapshot_ref:'snapshot:1',selection_ref:'selection:1',artifact_ref:'artifact:one',engine:'pandapower',engine_version:'3.4.0',scenario_revision:'scenario:one',mapped_elements:6,native_key_coverage_complete:true,covered_element_tables:['bus','line','load','trafo'],source_mapping_missing:1,elements:[...buses,line,stringLine,load,missing]}
  const view=electricalManifest();view.target=null;view.representation='calculation_bus_branch';view.artifact_ref=map.artifact_ref;view.derivation={artifact_ref:map.artifact_ref,engine:map.engine,engine_version:map.engine_version,scenario_revision:map.scenario_revision,demo_only:true,operating_scenario_verified:false}
  const batch:ElectricalResultBatch={model_ref:map.model_ref,model_revision:map.model_revision,artifact_ref:map.artifact_ref,engine:map.engine,engine_version:map.engine_version,scenario_revision:map.scenario_revision,authority_ref:'registered:test-authority',run_ref:'test-run',solver_status:'converged',rows:[{element_table:'line',element_key:45,metric:'loading_percent',value:72.5,unit:'%'}]}
  return {map,view,batch}
}
describe('released element map and admitted result binding',()=>{
  it('retains exact native indices, source equivalence, scenario origin, and unverified source roles',()=>{
    const {map}=fixture(),parsed=parseElectricalElementMap(map)
    expect(parsed.elements[2].label).toBe('7');expect(parsed.elements[2].element_key).toBe(45)
    expect(parsed.elements[2].endpoints.map(endpoint=>endpoint.element_key)).toEqual([7,29])
    expect(parsed.elements[2].endpoints.every(endpoint=>endpoint.source_port_mapping_status==='unavailable_or_ambiguous'&&!endpoint.source_port_refs.length)).toBe(true)
    expect(parsed.elements[0].source_refs).toEqual(['source:a','source:b']);expect(parsed.elements[4]).toMatchObject({origin:'scenario_created',source_refs:[]})
    expect(nativeElementIdentity('line',45)).not.toBe(nativeElementIdentity('line','45'))
  })
  it('binds integer and string keys separately and never matches a display name as a key',()=>{
    const {map,view,batch}=fixture();batch.rows.push({...batch.rows[0],element_key:'45',value:81},{...batch.rows[0],element_key:7,value:12})
    const bound=bindElectricalResults(map,batch,view)
    expect(bound.status).toBe('bound');if(bound.status!=='bound')throw new Error('expected binding')
    expect(bound.matches.map(match=>[match.status,match.element?.element_ref])).toEqual([['bound','line-native'],['bound','line-string'],['missing',undefined]])
    expect(bound.matches[0].result).toBe(batch.rows[0]);expect(bound.demo_only).toBe(true)
  })
  it.each(['model_ref','model_revision','artifact_ref','engine','engine_version','scenario_revision'] as const)('blocks a result from another %s',field=>{
    const {map,view,batch}=fixture();batch[field]='other'
    expect(bindElectricalResults(map,batch,view)).toEqual({status:'blocked',reason:'model_identity_mismatch',matches:[]})
  })
  it('blocks a different visible model and nonconverged or unattributed results',()=>{
    const {map,view,batch}=fixture()
    expect(bindElectricalResults(map,batch,{...view,artifact_ref:'other'})).toMatchObject({status:'blocked',reason:'view_identity_mismatch'})
    expect(bindElectricalResults(map,{...batch,solver_status:'not_converged'},view)).toMatchObject({status:'blocked',reason:'solver_not_converged'})
    expect(bindElectricalResults(map,{...batch,run_ref:''},view)).toMatchObject({status:'blocked',reason:'missing_authority_identity'})
    expect(bindElectricalResults(map,batch,{...view,derivation:{...view.derivation as object,scenario_revision:'different'}})).toMatchObject({status:'blocked',reason:'view_identity_mismatch'})
    expect(bindElectricalResults(map,batch,{...view,derivation:{...view.derivation as object,demo_only:undefined}})).toMatchObject({status:'blocked',reason:'view_identity_mismatch'})
  })
  it('reports missing source maps, conflicts, uncalculated values, omission and invalid values explicitly',()=>{
    const {map,view,batch}=fixture();const base=batch.rows[0]
    batch.rows=[{...base,element_table:'trafo',element_key:2},{...base,element_ref:'line-string'},{...base,element_key:900,element_ref:'line-native'},{...base,element_key:'45',value:null},{...base,element_table:'load',element_key:19,status:'omitted'},{...base,element_table:'bus',element_key:7,value:NaN}]
    const bound=bindElectricalResults(map,batch,view);if(bound.status!=='bound')throw new Error('expected binding')
    expect(bound.matches.map(match=>match.status)).toEqual(['source_mapping_missing','ambiguous','ambiguous','not_calculated','omitted','invalid'])
    expect(bound.matches[3].result.value).toBeNull()
  })
  it('does not let duplicate result identities overwrite one another',()=>{
    const {map,view,batch}=fixture();batch.rows.push({...batch.rows[0],value:99})
    const bound=bindElectricalResults(map,batch,view);if(bound.status!=='bound')throw new Error('expected binding')
    expect(bound.matches.map(match=>match.status)).toEqual(['ambiguous','ambiguous'])
  })
  it('rejects ambiguous map keys and mismatched typed endpoint references',()=>{
    const first=fixture().map;first.elements.push({...first.elements[2],element_ref:'duplicate-key'});first.mapped_elements++
    expect(()=>parseElectricalElementMap(first)).toThrow('ambiguous_native_key')
    const second=fixture().map;second.elements[2].endpoints[0].element_key='7'
    expect(()=>parseElectricalElementMap(second)).toThrow('endpoint_identity_mismatch')
    const third=fixture().map;third.elements[2].endpoints[0].source_port_mapping_status='mapped'
    expect(()=>parseElectricalElementMap(third)).toThrow('inconsistent_port_mapping')
    const fourth=fixture().map;fourth.elements[5].mapping_status='mapped'
    expect(()=>parseElectricalElementMap(fourth)).toThrow('inconsistent_source_mapping')
  })
  it('rejects corrupt coverage counts and enforces a processing budget without changing artifact identity',()=>{
    const {map}=fixture()
    expect(()=>parseElectricalElementMap({...map,mapped_elements:100})).toThrow('invalid_mapping_counts')
    expect(()=>parseElectricalElementMap({...map,source_mapping_missing:0})).toThrow('invalid_missing_count')
    expect(()=>parseElectricalElementMap(map,{maxElements:2})).toThrow('mapping_budget_exceeded')
  })
})
