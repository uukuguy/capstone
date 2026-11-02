import {it,expect} from 'vitest'
import {electricalSourceScene,sourceLabelVisible} from './electricalSourceScene'
import type {GridSourcePage,GridSourceView} from './gridSource'

it('shows meaningful equipment names but suppresses source junction IDs and missing names',()=>{
  expect(sourceLabelVisible({id:'node:123',kind:'connection_node',label:'node:123'})).toBe(false)
  expect(sourceLabelVisible({id:'bus:123',kind:'busbars'})).toBe(false)
  expect(sourceLabelVisible({id:'bus:123',kind:'busbars',label:'bus:123'})).toBe(false)
  expect(sourceLabelVisible({id:'bus:123',kind:'busbars',label:'500kV一母'})).toBe(true)
})

it('keeps source identities, real incidence and membership distinct without adding missing links',()=>{
  const nodes=[{id:'t',kind:'transformers'},{id:'w1',kind:'windings'},{id:'w2',kind:'windings'},{id:'w3',kind:'windings'},{id:'bus',kind:'busbars'},{id:'switch',kind:'breakers'},{id:'g',kind:'generators'},{id:'load',kind:'loads'},{id:'line',kind:'line'},{id:'terminal',kind:'terminal'}]
  const edges=[...['w1','w2','w3'].map(id=>({id:`member-${id}`,kind:'winding_membership',source:'t',target:id})),{id:'actual',kind:'source_connection',source:'bus',target:'switch'},{id:'line-member',kind:'line_terminal',source:'line',target:'terminal'}]
  const page:GridSourcePage={schema:'capstone-grid-source-topology/1',source_id:'gateway',view_ref:'immutable',level:'equipment',selected_object_id:'s',scope:{},selection:{},source_snapshot:{},provenance:{},nodes,edges,total_nodes:nodes.length,total_edges:edges.length,node_offset:0,edge_offset:0,next_node_offset:null,next_edge_offset:null,source_gaps:[],gaps:[],boundary_object_ids:[],display_grouping_only:false,electrical_equivalence_performed:false}
  const view:GridSourceView={page,nodes,edges,complete:true,unresolvedEndpoints:[]},scene=electricalSourceScene(view)
  expect(scene.nodes.map(n=>n.id)).toEqual(nodes.map(n=>n.id));expect(scene.edges.map(e=>e.id)).toEqual(edges.map(e=>e.id))
  expect(scene.nodes[0]).toMatchObject({kind:'transformers',symbolKind:'trafo3w'});expect(scene.nodes[5].switchState).toBe('unknown')
  expect(scene.edges.map(e=>e.relation)).toEqual(['membership','membership','membership','connection','membership'])
  expect(scene.edges.some(e=>['g','load'].includes(e.source)||['g','load'].includes(e.target))).toBe(false)
  expect(scene.nodes.every(n=>n.stationId===undefined)).toBe(true)
  expect(electricalSourceScene({...view,edges:edges.slice(1)}).nodes[0].symbolKind).toBeUndefined()
})
