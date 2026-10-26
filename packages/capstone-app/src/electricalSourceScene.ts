import type {GridSourceView} from './gridSource'
import type {NetworkScene} from './networkScene'

/** Source records remain source records: this adapter creates no electrical facts. */
export function electricalSourceScene(view:GridSourceView):NetworkScene {
  const ids=new Set(view.nodes.map(node=>node.id))
  const windingCounts=new Map<string,Set<string>>()
  const kinds=new Map(view.nodes.map(node=>[node.id,node.kind]))
  for(const edge of view.edges)if(edge.kind==='winding_membership'&&edge.source&&edge.target){
    const transformer=['transformer','transformers'].includes(kinds.get(edge.source)||'')?edge.source:['transformer','transformers'].includes(kinds.get(edge.target)||'')?edge.target:undefined
    const winding=transformer===edge.source?edge.target:edge.source
    if(transformer&&['winding','windings'].includes(kinds.get(winding)||'')){const members=windingCounts.get(transformer)||new Set<string>();members.add(winding);windingCounts.set(transformer,members)}
  }
  return {ref:view.page.view_ref,coordinateSystem:'schematic',displayMode:'source-electrical',
    nodes:view.nodes.map(node=>({id:node.id,label:node.label||node.id,kind:node.kind,
      sourceRef:node.source_id,stationId:node.station_id??undefined,parentId:node.parent_id??undefined,
      boundary:node.boundary,voltageKv:node.voltage_kv??node.vn_kv,
      symbolKind:windingCounts.get(node.id)?.size===3?'trafo3w':undefined,
      switchState:['breaker','breakers','disconnector','disconnectors','switch','ground_disconnector','ground_disconnectors'].includes(node.kind)?'unknown':undefined,
      details:[{label:'来源对象',value:node.id},{label:'图形约定',value:'源模型单线图；未推断端子角色或开关状态'}]})),
    edges:view.edges.filter(edge=>edge.source&&edge.target&&ids.has(edge.source)&&ids.has(edge.target)).map(edge=>({
      id:edge.id,source:edge.source!,target:edge.target!,kind:edge.kind,label:edge.label||edge.id,sourceRef:edge.source_id,
      relation:['winding_membership','line_terminal'].includes(edge.kind)?'membership':edge.kind==='source_connection'?'connection':'unresolved',
      details:[{label:'关系类型',value:edge.kind}]}))}
}
