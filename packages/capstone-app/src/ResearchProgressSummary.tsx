import type {GraphNode} from './executionGraph'
type Node=Pick<GraphNode,'id'|'purpose'|'phase'|'applicability'>
/** Business state comes from admitted tasks, never a guessed percentage. */
export default function ResearchProgressSummary({nodes,limitations,running}:{nodes:readonly Node[];limitations:readonly string[];running:boolean}){
  const current=nodes.filter(node=>node.applicability==='current')
  const completed=current.filter(node=>['success','limited'].includes(node.phase))
  const active=current.filter(node=>node.phase==='executing')
  const returned=current.some(node=>['executed','recorded','assessing'].includes(node.phase))
  const failed=current.filter(node=>node.phase==='failure')
  const notes=[...new Set(limitations.filter(Boolean))]
  return <section className="capstone-research-summary" aria-label="研究进展">
    <p><strong>研究进展</strong><span>已完成 {completed.length} / {current.length} 项</span></p>
    {running&&<div aria-live="polite"><span>{active.length?'正在进行':returned?'研究结果已返回，等待接收':completed.length===current.length?'研究任务已结束，正在准备交付':'正在安排后续研究'}</span>{active.map(node=><div key={node.id}>{node.purpose}</div>)}</div>}
    {completed.length>0&&<details><summary>已完成的研究 · {completed.length}</summary><ul>{completed.map(node=><li key={node.id}>{node.purpose}{node.phase==='limited'?'（含限制）':''}</li>)}</ul></details>}
    {failed.length>0&&<p>尚未完成：{failed.map(node=>node.purpose).join('、')}</p>}
    {notes.length>0&&<details><summary>已记录缺口 · {notes.length}</summary><ul>{notes.map(note=><li key={note}>{note}</li>)}</ul></details>}
  </section>
}
