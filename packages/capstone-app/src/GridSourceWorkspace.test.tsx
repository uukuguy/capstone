import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { HttpThreadTransport } from './threadHttpTransport'
import GridSourceWorkspace from './GridSourceWorkspace'
import { SessionReadingProvider } from './workspaceSessionCache'
import type { ThreadSourceViewRequest } from './threadViewRouting'

vi.mock('./LargeNetworkView',()=>({LargeNetworkView:({scene,onActivate}:{scene:{nodes:{id:string}[];edges:unknown[]};onActivate:(node:{id:string})=>void})=>
  <button onClick={()=>onActivate(scene.nodes[0])}>展开节点（{scene.edges.length}条可定位连接）</button>}))
const page={schema:'capstone-grid-source-topology/1',source_id:'data-gateway',view_ref:'north-view',level:null,
  selected_object_id:null,scope:{scope_id:'north'},selection:{boundary_policy:'retain_external_stub'},source_snapshot:{metadata_snapshot:'source-a',source_instance:'source-1'},provenance:{},
  nodes:[{id:'station:a',kind:'station',label:'站点甲',expand:{level:'station',selected_object_id:'station:a'}}],
  edges:[{id:'line:a',source:'station:a',target:'missing',kind:'source_line'}],total_nodes:1,total_edges:1,
  node_offset:0,edge_offset:0,next_node_offset:null,next_edge_offset:null,source_gaps:['switch_positions_unverified'],gaps:[],boundary_object_ids:[],
  display_grouping_only:false,electrical_equivalence_performed:false}
describe('source workspace',()=>{
  afterEach(cleanup)
  it('loads the exact admitted instruction scope and snapshot, then lets manual navigation win',async()=>{
    const requestedView:ThreadSourceViewRequest={schema:'capstone-grid-source-view-request/1',source_id:'data-gateway',
      scope_id:'other-region',scope_name:'指定区域',level:'station',selected_object_id:'station:chosen',view_ref:'chosen-view',
      source_snapshot:{metadata_snapshot:'source-a',source_instance:'source-1'},voltage_min_kv:220,display_grouping_only:true}
    const read=vi.fn().mockImplementation(async query=>({...page,scope:{scope_id:query.scope_id},level:query.level,
      selected_object_id:query.selected_object_id||null,display_grouping_only:query.level!==null,
      view_ref:query.expected_view_ref||'manual-view',selection:{min_ac_kv:query.voltage_min_kv}}))
    const manual=vi.fn(),transport={gridSourceTopology:read} as unknown as HttpThreadTransport
    const result=render(<GridSourceWorkspace transport={transport} requestedView={requestedView} requestNonce={1} onManualNavigate={manual} onQuestion={vi.fn()}/>)
    await waitFor(()=>expect(read.mock.calls.at(-1)?.[0]).toMatchObject({scope_id:'other-region',level:'station',selected_object_id:'station:chosen',expected_view_ref:'chosen-view',voltage_min_kv:220}))
    expect(await screen.findByText('展开节点（0条可定位连接）')).toBeTruthy()
    fireEvent.click(screen.getByRole('button',{name:'站点总览'}))
    await waitFor(()=>expect(read.mock.calls.at(-1)?.[0]).toMatchObject({scope_id:'other-region',level:'region',voltage_min_kv:220}))
    expect(manual).toHaveBeenCalledOnce()
    result.rerender(<GridSourceWorkspace transport={transport} requestedView={{...requestedView}} requestNonce={1} onManualNavigate={manual} onQuestion={vi.fn()}/>)
    expect(read.mock.calls.at(-1)?.[0].level).toBe('region')
    result.rerender(<GridSourceWorkspace transport={transport} requestedView={requestedView} requestNonce={2} onManualNavigate={manual} onQuestion={vi.fn()}/>)
    await waitFor(()=>expect(read.mock.calls.at(-1)?.[0].expected_view_ref).toBe('chosen-view'))
  })
  it('retains source counts while omitting unresolved geometry, and hands off the exact accepted source view',async()=>{
    const read=vi.fn().mockResolvedValue(page),ask=vi.fn().mockResolvedValue(undefined)
    render(<GridSourceWorkspace transport={{gridSourceTopology:read} as unknown as HttpThreadTransport} onQuestion={ask}/>)
    expect(await screen.findByText('展开节点（0条可定位连接）')).toBeTruthy()
    expect(screen.getByText(/1 个源节点 · 1 条源连接 · 未定位端点 1/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button',{name:'在独立源拓扑会话中提问'}))
    await waitFor(()=>expect(ask).toHaveBeenCalledTimes(1))
    expect(ask.mock.calls[0][0]).toMatchObject({page:{view_ref:'north-view'},unresolvedEndpoints:['missing']})
  })
  it('refuses a drill-down from a different source snapshot',async()=>{
    const read=vi.fn().mockResolvedValueOnce(page).mockResolvedValueOnce({...page,view_ref:'station-view',level:'station',selected_object_id:'station:a',display_grouping_only:true,
      source_snapshot:{metadata_snapshot:'source-b',source_instance:'source-1'}})
    render(<GridSourceWorkspace transport={{gridSourceTopology:read} as unknown as HttpThreadTransport} onQuestion={vi.fn()}/>)
    fireEvent.click(await screen.findByText('展开节点（0条可定位连接）'))
    expect((await screen.findByRole('alert')).textContent).toContain('来源快照已变化')
    expect(read.mock.calls[1][0]).toMatchObject({scope_id:'north',level:'station',selected_object_id:'station:a'})
    expect(read.mock.calls[1][0].expected_view_ref).toBeUndefined()
  })
  it('refuses a drill-down whose published selection rule changes',async()=>{
    const read=vi.fn().mockResolvedValueOnce({...page,selection:{rule_sha256:'rule-a'}}).mockResolvedValueOnce({
      ...page,level:'station',selected_object_id:'station:a',display_grouping_only:true,view_ref:'station-view',selection:{rule_sha256:'rule-b'},
    })
    render(<GridSourceWorkspace transport={{gridSourceTopology:read} as unknown as HttpThreadTransport} onQuestion={vi.fn()}/>)
    fireEvent.click(await screen.findByText('展开节点（0条可定位连接）'))
    expect((await screen.findByRole('alert')).textContent).toContain('来源选择规则已变化')
  })
  it('keeps the selected source object when switching resource tabs within the same session',async()=>{
    const read=vi.fn().mockImplementation(async query=>({...page,level:query.level,display_grouping_only:query.level!==null,selected_object_id:query.selected_object_id||null}))
    const transport={gridSourceTopology:read} as unknown as HttpThreadTransport
    const content=(open:boolean)=><SessionReadingProvider namespace="source-restore" threadId="thr_source_restore">{open&&<GridSourceWorkspace transport={transport} onQuestion={vi.fn()}/>}</SessionReadingProvider>
    const result=render(content(true))
    fireEvent.click(await screen.findByText('展开节点（0条可定位连接）'))
    await waitFor(()=>expect(read.mock.calls.at(-1)?.[0].selected_object_id).toBe('station:a'))
    result.rerender(content(false));result.rerender(content(true))
    await waitFor(()=>expect(read.mock.calls.at(-1)?.[0]).toMatchObject({level:'station',selected_object_id:'station:a'}))
    expect(screen.getByRole('button',{name:'站点甲'})).toBeTruthy()
  })
})
