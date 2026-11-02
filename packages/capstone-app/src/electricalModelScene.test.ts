import {it,expect} from 'vitest'
import {electricalModelScene} from './electricalModelScene'
import {loadElectricalModelView} from './electricalModelView'
import {electricalRecords,electricalManifest,electricalPage,electricalOverviewRecords,electricalOverviewManifest} from './electricalModelFixtures'
import {buildSceneIndex,sceneGeometry} from './networkSceneIndex'

it('keeps real port incidence distinct from device ownership and hides internal labels',async()=>{
  const records=electricalRecords();records.devices.push({id:'generator',kind:'generator',name:'Generator'},{id:'load',kind:'load',name:'Load'})
  const manifest=electricalManifest(records),view=await loadElectricalModelView(manifest,async request=>electricalPage(manifest,records,request),{mode:'closure'})
  const scene=electricalModelScene(view)
  expect(scene.nodes.map(node=>node.id)).toEqual(['device','generator','load','p1','p2','j1','j2'])
  expect(scene.edges.some(edge=>['generator','load'].includes(edge.source)||['generator','load'].includes(edge.target))).toBe(false)
  expect(scene.edges.filter(edge=>edge.relation==='connection').map(edge=>[edge.id,edge.source,edge.target])).toEqual([['c1','p1','j1'],['c2','p2','j2']])
  expect(scene.edges.filter(edge=>edge.kind==='port_ownership')).toHaveLength(2)
  expect(scene.edges.filter(edge=>edge.kind==='port_ownership').every(edge=>edge.relation==='membership'&&edge.details?.some(detail=>detail.value==='ports.device_id'))).toBe(true)
  expect(scene.nodes[0]).toMatchObject({label:'Breaker A',showLabel:true,switchState:'unknown'})
  expect(scene.nodes.slice(3).every(node=>node.showLabel===false)).toBe(true)
  expect(scene.nodes.find(node=>node.id==='p2')).toMatchObject({boundary:true,parentId:'device'})
  expect(scene.nodes.find(node=>node.id==='p1')?.details).toContainEqual({label:'端子角色',value:'未核准'})
  const index=buildSceneIndex(scene);expect(sceneGeometry(index)?.routes.size).toBe(4)
})
it('uses declared composition IDs and does not duplicate a published port ownership relation',async()=>{
  const records=electricalRecords();records.device_relations.push({id:'relation:port',parent_id:'device',child_id:'p1',child_stream:'ports',kind:'line_terminal_membership',electrical_connection:false})
  const manifest=electricalManifest(records),view=await loadElectricalModelView(manifest,async request=>electricalPage(manifest,records,request),{mode:'closure'}),scene=electricalModelScene(view)
  expect(scene.edges.find(edge=>edge.id==='relation:port')).toMatchObject({source:'device',target:'p1',relation:'membership'})
  expect(scene.edges.filter(edge=>edge.source==='device'&&edge.target==='p1')).toHaveLength(1)
  records.devices[0].switch_position={value:'closed',verified:true}
  expect(electricalModelScene(view).nodes[0].switchState).toBe('closed')
})
it('keeps the root projection a station directory without electrical edges',async()=>{
  const records=electricalRecords(),manifest=electricalManifest(records,null),view=await loadElectricalModelView(manifest,async request=>electricalPage(manifest,records,request),{mode:'groups'}),scene=electricalModelScene(view)
  expect(scene.nodes).toHaveLength(1);expect(scene.nodes[0].kind).toBe('station');expect(scene.edges).toEqual([])
  expect(()=>electricalModelScene({...view,complete:false})).toThrow('incomplete_view')
})
it('projects a published calculation bus alias once without changing its element identity',async()=>{
  const records=electricalRecords();records.devices.push({id:'j1',kind:'bus',name:'Bus name 16',element_key:7,origin:'source_equivalence'});records.connectivity_nodes[0].kind='calculation_bus'
  const manifest=electricalManifest(records,null);manifest.representation='calculation_bus_branch';manifest.artifact_ref='artifact:one'
  const view=await loadElectricalModelView(manifest,async request=>electricalPage(manifest,records,request),{mode:'closure'}),scene=electricalModelScene(view)
  expect(scene.nodes.filter(node=>node.id==='j1')).toHaveLength(1)
  expect(scene.nodes.find(node=>node.id==='j1')).toMatchObject({kind:'bus',label:'Bus name 16',voltageKv:110})
  expect(scene.nodes.find(node=>node.id==='j1')?.details).toContainEqual({label:'引擎元素键',value:'number: 7'})
  expect(scene.nodes.find(node=>node.id==='j1')?.details).toContainEqual({label:'元素来源',value:'source_equivalence'})
  expect(scene.edges.find(edge=>edge.id==='c1')?.target).toBe('j1')
  expect(()=>buildSceneIndex(scene)).not.toThrow()
})
it('projects actual summary IDs, boundary groups and declared line endpoints without conducting edges',async()=>{
  const records=electricalOverviewRecords(),manifest=electricalOverviewManifest(records)
  const view=await loadElectricalModelView(manifest,async request=>electricalPage(manifest,records,request),{mode:'overview'}),scene=electricalModelScene(view)
  expect(scene.displayMode).toBe('source-regional')
  expect(scene.nodes.map(node=>node.id)).toEqual(records.summary_nodes.map(node=>node.id))
  expect(scene.edges.map(edge=>[edge.id,edge.source,edge.target])).toEqual(records.summary_edges.map(edge=>[edge.id,edge.source_id,edge.target_id]))
  expect(scene.nodes.find(node=>node.id==='group:grid')).toMatchObject({kind:'grid',symbolKind:'voltage_group',label:'Region A'})
  expect(scene.nodes.find(node=>node.id==='group:station')).toMatchObject({kind:'station',label:'Station A',showLabel:true})
  expect(scene.nodes.find(node=>node.id==='group:outside')).toMatchObject({boundary:true,symbolKind:'boundary',showLabel:false})
  expect(scene.edges.every(edge=>edge.relation==='unresolved'&&edge.kind==='source_ac_line_station_endpoints')).toBe(true)
  expect(scene.edges[0]).toMatchObject({label:'2 条源线路'})
  expect(scene.edges[0].details).toContainEqual({label:'电气连通',value:'未核验；不是电气等值'})
  expect(scene.nodes[1].details).toContainEqual({label:'源对象 ID',value:'station-source'})
  expect(()=>buildSceneIndex(scene)).not.toThrow()
  view.records.summary_edges[0].target_id='missing'
  expect(()=>electricalModelScene(view)).toThrow('missing_summary_endpoint')
})
it('retains station symbols and source identity through v2 detail projection',async()=>{
  const records=electricalRecords();records.devices.push({id:'bar',kind:'busbar',name:'Busbar A',source_ref:{source_instance:'source:a',table:'BUSBAR',object_id:'bar-source'}},{id:'transformer',kind:'transformer',name:'Transformer A'},...['high','middle','low'].map(id=>({id,kind:'winding',name:`Winding ${id}`})))
  records.device_relations.push(...['high','middle','low'].map(id=>({id:`relation:${id}`,parent_id:'transformer',child_id:id,child_stream:'devices' as const,kind:'winding_membership',electrical_connection:false as const})))
  const manifest=electricalOverviewManifest(records);manifest.target='station'
  const view=await loadElectricalModelView(manifest,async request=>electricalPage(manifest,records,request),{mode:'closure'}),scene=electricalModelScene(view)
  expect(scene.nodes.find(node=>node.id==='bar')).toMatchObject({kind:'busbar',label:'Busbar A'})
  expect(scene.nodes.find(node=>node.id==='bar')?.details).toContainEqual({label:'源对象 ID',value:'bar-source'})
  expect(scene.nodes.find(node=>node.id==='transformer')).toMatchObject({symbolKind:'trafo3w'})
  expect(scene.nodes.find(node=>node.id==='device')).toMatchObject({switchState:'unknown'})
  expect(scene.nodes.find(node=>node.id==='p1')).toMatchObject({symbolKind:'terminal',showLabel:false})
  expect(scene.edges.filter(edge=>edge.relation==='connection').map(edge=>edge.id)).toEqual(['c1','c2'])
})
