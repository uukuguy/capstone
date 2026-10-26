import {useMemo} from 'react'
import type {NetworkScene} from './networkScene'
import {networkSymbol,sceneGlyphs,type NetworkSymbol} from './networkSymbols'

export function NetworkSymbolIcon({symbol}:{symbol:NetworkSymbol}){
  return <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><path d={symbol.path} fill={symbol.code===0?'currentColor':'none'} stroke="currentColor" strokeWidth={symbol.code===1?3:1.4} strokeLinecap="round" strokeLinejoin="round"/></svg>
}
export default function NetworkLegend({scene}:{scene:NetworkScene}){
  const entries=useMemo(()=>{
    const kinds=new Map<string,number>()
    for(const node of scene.nodes)kinds.set(node.kind,(kinds.get(node.kind)||0)+1)
    const symbols=[...kinds].map(([kind,count])=>({symbol:networkSymbol(kind),count}))
    const boundaries=scene.nodes.filter(node=>node.boundary).length
    if(boundaries)symbols.push({symbol:sceneGlyphs.boundaryHalo,count:boundaries})
    const transformers=scene.edges.filter(edge=>['transformer','transformers','trafo','trafo3w'].includes(edge.kind)).length
    if(transformers&&!symbols.some(item=>item.symbol.code===2))symbols.push({symbol:sceneGlyphs.transformer,count:transformers})
    return symbols
  },[scene])
  return <details className="network-symbol-legend" open><summary>符号图例</summary><div aria-label="拓扑符号图例">
    {entries.map(({symbol,count},i)=><span key={`${symbol.code}:${i}`}><NetworkSymbolIcon symbol={symbol}/>{symbol.label} <small>{count}</small></span>)}
    {scene.displayMode==='source-electrical'?<>
      <span>源连接 <small>{scene.edges.filter(edge=>edge.relation==='connection').length}</small></span>
      <span>构成与归属（非导通） <small>{scene.edges.filter(edge=>edge.relation==='membership').length}</small></span>
    </>:scene.edges.length>0&&<span><svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><path d="M 2 10 H 18" stroke="currentColor"/></svg>{scene.displayMode==='source-regional'?'源线路（可聚束）':scene.displayMode==='source-detail'?'源端子 / 连接关系':'线路 / 连接'} <small>{scene.edges.length}</small></span>}
  </div>{scene.displayMode?.startsWith('source')&&<p>按来源类别示意；开关符号不表示开合状态。</p>}</details>
}
