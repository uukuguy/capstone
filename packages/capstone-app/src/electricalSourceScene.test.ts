import {it,expect} from 'vitest'
import {electricalSourceScene} from './electricalSourceScene'
import type {GridSourcePage,GridSourceView} from './gridSource'

it('keeps source identities, real incidence and membership distinct without adding missing links',()=>{
  const nodes=[{id:'t',kind:'transformers'},{id:'w1',kind:'windings'},{id:'w2',kind:'windings'},{id:'w3',kind:'windings'},{id:'bus',kind:'busbars'},{id:'switch',kind:'breakers'},{id:'g',kind:'generators'},{id:'load',kind:'loads'}]
  const edges=[...['w1','w2','w3'].map(id=>({id:`member-${id}`,kind:'winding_membership',source:'t',target:id})),{id:'actual',kind:'source_connection',source:'bus',target:'switch'}]
  const page:GridSourcePage={schema:'capstone-grid-source-topology/1',source_id:'gateway',view_ref:'immutable',level:'equipment',selected_object_id:'s',scope:{},selection:{},source_snapshot:{},provenance:{},nodes,edges,total_nodes:nodes.length,total_edges:edges.length,node_offset:0,edge_offset:0,next_node_offset:null,next_edge_offset:null,source_gaps:[],gaps:[],boundary_object_ids:[],display_grouping_only:false,electrical_equivalence_performed:false}
  const view:GridSourceView={page,nodes,edges,complete:true,unresolvedEndpoints:[]},scene=electricalSourceScene(view)
  expect(scene.nodes.map(n=>n.id)).toEqual(nodes.map(n=>n.id));expect(scene.edges.map(e=>e.id)).toEqual(edges.map(e=>e.id))
  expect(scene.nodes[0]).toMatchObject({kind:'transformers',symbolKind:'trafo3w'});expect(scene.nodes[5].switchState).toBe('unknown')
  expect(scene.edges.map(e=>e.relation)).toEqual(['membership','membership','membership','connection'])
  expect(scene.edges.some(e=>['g','load'].includes(e.source)||['g','load'].includes(e.target))).toBe(false)
  expect(scene.nodes.every(n=>n.stationId===undefined)).toBe(true)
  expect(electricalSourceScene({...view,edges:edges.slice(1)}).nodes[0].symbolKind).toBeUndefined()
})
