import {it,expect} from 'vitest'
import {electricalModelScene} from './electricalModelScene'
import {loadElectricalModelView} from './electricalModelView'
import {electricalRecords,electricalManifest,electricalPage} from './electricalModelFixtures'
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
