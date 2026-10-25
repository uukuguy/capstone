/** Source display records. These are not admitted electrical calculation models. */
export type GridSourceLevel = 'region' | 'station' | 'equipment'
export type GridSourceObject = {
  id: string; kind: string; label?: string; source_id?: string; boundary?: boolean
  source?: string; target?: string
  expand?: { level: GridSourceLevel; selected_object_id: string } | null
}
export type GridSourcePage = {
  schema: 'capstone-grid-source-topology/1'; source_id: string; view_ref: string
  level: GridSourceLevel; selected_object_id: string | null
  scope: Record<string, unknown>; selection: Record<string, unknown>
  source_snapshot: Record<string, unknown>; provenance: Record<string, unknown>
  nodes: GridSourceObject[]; edges: GridSourceObject[]
  total_nodes: number; total_edges: number; node_offset: number; edge_offset: number
  next_node_offset: number | null; next_edge_offset: number | null
  source_gaps: unknown[]; gaps: unknown[]; boundary_object_ids: string[]
  display_grouping_only: true; electrical_equivalence_performed: false
}
export type GridSourceQuery = {
  scope_id: string; level?: GridSourceLevel; selected_object_id?: string | null
  voltage_min_kv?: number | null; node_offset?: number; edge_offset?: number
  limit?: number; expected_view_ref?: string
}
export type GridSourceView = {
  page: GridSourcePage; nodes: GridSourceObject[]; edges: GridSourceObject[]
  unresolvedEndpoints: string[]; complete: boolean
}
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const integer = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0

export function parseGridSourcePage(value: unknown): GridSourcePage {
  if (!record(value) || value.schema !== 'capstone-grid-source-topology/1'
      || typeof value.view_ref !== 'string' || !value.view_ref || value.source_id !== 'data-gateway'
      || !['region', 'station', 'equipment'].includes(String(value.level))
      || value.display_grouping_only !== true || value.electrical_equivalence_performed !== false)
    throw new Error('源拓扑响应无效。')
  for (const key of ['scope', 'selection', 'source_snapshot', 'provenance'])
    if (!record(value[key])) throw new Error('源拓扑缺少来源信息。')
  for (const key of ['total_nodes', 'total_edges', 'node_offset', 'edge_offset'])
    if (!integer(value[key])) throw new Error('源拓扑分页无效。')
  for (const key of ['next_node_offset', 'next_edge_offset'])
    if (value[key] !== null && !integer(value[key])) throw new Error('源拓扑游标无效。')
  for (const key of ['nodes', 'edges']) {
    const entries = value[key]
    if (!Array.isArray(entries) || entries.length > 1000) throw new Error('源拓扑页超过读取范围。')
    const ids = new Set<string>()
    for (const entry of entries) {
      if (!record(entry) || typeof entry.id !== 'string' || !entry.id || typeof entry.kind !== 'string'
          || ids.has(entry.id) || (key === 'edges' && (typeof entry.source !== 'string' || typeof entry.target !== 'string')))
        throw new Error('源拓扑对象无效或重复。')
      if (entry.expand != null && (!record(entry.expand) || !['region','station','equipment'].includes(String(entry.expand.level))
          || typeof entry.expand.selected_object_id !== 'string')) throw new Error('源拓扑展开引用无效。')
      ids.add(entry.id)
    }
  }
  for (const key of ['source_gaps', 'gaps', 'boundary_object_ids'])
    if (!Array.isArray(value[key])) throw new Error('源拓扑缺少质量记录。')
  return value as GridSourcePage
}

/** Separate streams may repeat the exhausted stream's last page. Never confuse
 * an edge whose endpoint is on a later page with an invalid electrical link. */
export async function loadGridSourceView(
  read: (query: GridSourceQuery, signal?: AbortSignal) => Promise<unknown>,
  query: GridSourceQuery, signal?: AbortSignal,
  onProgress?: (nodes: number, edges: number) => void,
): Promise<GridSourceView> {
  const nodes = new Map<string, GridSourceObject>(), edges = new Map<string, GridSourceObject>()
  const sourceGaps = new Map<string,unknown>(), gaps = new Map<string,unknown>(), boundaries = new Set<string>()
  let first: GridSourcePage | undefined, nodeOffset = 0, edgeOffset = 0
  let nodeDone = false, edgeDone = false
  for (let pageCount = 0; pageCount < 2000; pageCount++) {
    signal?.throwIfAborted()
    const page = parseGridSourcePage(await read({ ...query, node_offset: nodeOffset, edge_offset: edgeOffset,
      limit: 1000, ...(first ? { expected_view_ref: first.view_ref } : {}) }, signal))
    signal?.throwIfAborted()
    if (!first) first = page
    if (page.view_ref !== first.view_ref || page.total_nodes !== first.total_nodes || page.total_edges !== first.total_edges
        || page.level !== first.level || page.node_offset !== nodeOffset || page.edge_offset !== edgeOffset
        || JSON.stringify(page.source_snapshot)!==JSON.stringify(first.source_snapshot)
        || JSON.stringify(page.selection)!==JSON.stringify(first.selection) || JSON.stringify(page.scope)!==JSON.stringify(first.scope))
      throw new Error('源拓扑版本或分页发生变化，请重新加载。')
    for(const item of page.source_gaps)sourceGaps.set(JSON.stringify(item),item)
    for(const item of page.gaps)gaps.set(JSON.stringify(item),item)
    for(const id of page.boundary_object_ids){
      if(typeof id!=='string')throw new Error('源拓扑边界引用无效。')
      boundaries.add(id)
    }
    if (page.total_nodes > 250_000 || page.total_edges > 500_000)
      throw new Error('此视图超过交互读取预算，请选择站点或设备范围。')
    for (const [entries, target] of [[page.nodes, nodes], [page.edges, edges]] as const)
      for (const entry of entries) {
        const prior = target.get(entry.id)
        if (prior && JSON.stringify(prior) !== JSON.stringify(entry)) throw new Error('同一源对象在分页中发生变化。')
        target.set(entry.id, entry)
      }
    onProgress?.(nodes.size, edges.size)
    if (page.next_node_offset !== null && !nodeDone) {
      if (page.next_node_offset <= nodeOffset) throw new Error('源节点游标没有前进。')
      nodeOffset = page.next_node_offset
    } else nodeDone = true
    if (page.next_edge_offset !== null && !edgeDone) {
      if (page.next_edge_offset <= edgeOffset) throw new Error('源线路游标没有前进。')
      edgeOffset = page.next_edge_offset
    } else edgeDone = true
    if (nodeDone && edgeDone) {
      if (nodes.size !== first.total_nodes || edges.size !== first.total_edges)
        throw new Error('源拓扑页数与声明总数不一致。')
      const unresolved = new Set<string>()
      for (const edge of edges.values()) for (const id of [edge.source!, edge.target!]) if (!nodes.has(id)) unresolved.add(id)
      return { page: {...first,source_gaps:[...sourceGaps.values()],gaps:[...gaps.values()],boundary_object_ids:[...boundaries]}, nodes: [...nodes.values()], edges: [...edges.values()],
        unresolvedEndpoints: [...unresolved], complete: true }
    }
  }
  throw new Error('源拓扑分页未在读取预算内完成。')
}
