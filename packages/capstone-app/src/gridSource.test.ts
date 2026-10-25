import { describe, expect, it } from 'vitest'
import { loadGridSourceView, type GridSourcePage } from './gridSource'
import { HttpThreadTransport } from './threadHttpTransport'

const node = (id: string) => ({id,kind:'station',label:id})
function page(overrides: Partial<GridSourcePage> = {}): GridSourcePage {
  return {schema:'capstone-grid-source-topology/1',source_id:'data-gateway',view_ref:'snapshot-a',level:'region',
    selected_object_id:null,scope:{scope_id:'north'},selection:{},source_snapshot:{},provenance:{},
    nodes:[node('a')],edges:[{id:'line1',kind:'source_line',source:'a',target:'b'}],total_nodes:2,total_edges:1,
    node_offset:0,edge_offset:0,next_node_offset:1,next_edge_offset:null,source_gaps:[],gaps:[],boundary_object_ids:[],
    display_grouping_only:true,electrical_equivalence_performed:false,...overrides}
}
describe('source topology paging', () => {
  it('loads ungrouped raw electrical-source objects without asserting bus reduction',async()=>{
    const result=await loadGridSourceView(async()=>page({level:null,display_grouping_only:false,total_nodes:1,next_node_offset:null}),{scope_id:'north',level:null})
    expect(result.page.level).toBeNull()
    expect(result.page.display_grouping_only).toBe(false)
    expect(result.page.electrical_equivalence_performed).toBe(false)
    await expect(loadGridSourceView(async()=>page({total_nodes:1,next_node_offset:null}),{scope_id:'north',level:null})).rejects.toThrow('本次请求')
  })
  it('uses the application source contract without requiring a Thread protocol response header',async()=>{
    const fetcher=(async()=>new Response(JSON.stringify(page()),{status:200,headers:{'Content-Type':'application/json'}})) as typeof fetch
    const transport=new HttpThreadTransport('http://localhost:8767','',fetcher,'/api/v1/threads','2')
    expect((await transport.gridSourceTopology({scope_id:'north'})).view_ref).toBe('snapshot-a')
    await expect(transport.getSnapshot('thr_example')).rejects.toThrow('协议版本不兼容')
  })
  it('reports source availability failures without exposing internal service errors',async()=>{
    const fetcher=(async()=>new Response(JSON.stringify({detail:'grid_source_response_invalid'}),{status:503})) as typeof fetch
    const transport=new HttpThreadTransport('http://localhost:8767','',fetcher,'/api/v1/threads','2')
    await expect(transport.gridSourceTopology({scope_id:'north'})).rejects.toThrow('源拓扑暂时无法读取')
  })
  it('loads both streams under the same revision and resolves later endpoints without collapsing parallel circuits',async()=>{
    const queries: unknown[]=[]
    const result=await loadGridSourceView(async query=>{
      queries.push(query)
      const edges=[{id:'line1',kind:'source_line',source:'a',target:'b'}, {id:'line2',kind:'source_line',source:'a',target:'b'}]
      return queries.length===1?page({edges,total_edges:2}):page({nodes:[node('b')],edges,total_edges:2,node_offset:1,next_node_offset:null})
    },{scope_id:'north'})
    expect(queries).toHaveLength(2)
    expect(queries[1]).toMatchObject({expected_view_ref:'snapshot-a',node_offset:1,edge_offset:0})
    expect(result.nodes.map(item=>item.id)).toEqual(['a','b'])
    expect(result.edges).toHaveLength(2)
    expect(result.unresolvedEndpoints).toEqual([])
  })
  it('rejects changed revisions and stalled cursors rather than retry indefinitely',async()=>{
    let calls=0
    await expect(loadGridSourceView(async()=>++calls===1?page():page({view_ref:'snapshot-b',node_offset:1}),{scope_id:'north'})).rejects.toThrow('版本')
    expect(calls).toBe(2)
    await expect(loadGridSourceView(async()=>page({next_node_offset:0}),{scope_id:'north'})).rejects.toThrow('没有前进')
  })
  it('retains missing endpoint quality and rejects misleading completeness',async()=>{
    const result=await loadGridSourceView(async()=>page({total_nodes:1,next_node_offset:null}),{scope_id:'north'})
    expect(result.unresolvedEndpoints).toEqual(['b'])
    await expect(loadGridSourceView(async()=>page({next_node_offset:null}),{scope_id:'north'})).rejects.toThrow('总数')
  })
  it('cancels stale loads before issuing a request',async()=>{
    const controller=new AbortController();controller.abort()
    let calls=0
    await expect(loadGridSourceView(async()=>{calls++;return page()},{scope_id:'north'},controller.signal)).rejects.toThrow()
    expect(calls).toBe(0)
  })
  it('retains gaps and boundary IDs discovered on subsequent pages',async()=>{
    let calls=0
    const result=await loadGridSourceView(async()=>++calls===1?page({source_gaps:['initial']}):page({
      nodes:[node('b')],node_offset:1,next_node_offset:null,source_gaps:['initial','later'],
      gaps:[{code:'source_incomplete'}],boundary_object_ids:['external'],
    }),{scope_id:'north'})
    expect(result.page.source_gaps).toEqual(['initial','later'])
    expect(result.page.gaps).toEqual([{code:'source_incomplete'}])
    expect(result.page.boundary_object_ids).toEqual(['external'])
  })
})
