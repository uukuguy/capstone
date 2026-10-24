import {applicationCapacity,exceedsCapacity,type CapacityKey} from './applicationCapacity'
type Claim = { claim_id: string; statement: string; status: 'pending' | 'supported' | 'refuted'; refs: string[] }
type Note = { note_id: string; text: string; refs: string[] }
export type ResearchSnapshot = { research_id: string; revision: number; goal: string;
  condition_refs: string[]; claims: Claim[]; notes: Note[]; open_questions: string[] }
const text = (value: unknown, max: number): value is string => typeof value === 'string' && value.length > 0 && value.length <= max
const boundedText=(value:unknown,key:CapacityKey):value is string=>typeof value==='string'&&value.length>0&&!exceedsCapacity(value.length,key)
const strings = (value: unknown, count: number, length: number): value is string[] =>
  Array.isArray(value) && !exceedsCapacity(value.length,'context_references') && value.length <= count && value.every(item => text(item, length))
const record = (value: unknown): value is Record<string, unknown> => Boolean(value && typeof value === 'object' && !Array.isArray(value))

export function parseResearchSnapshot(value: unknown): ResearchSnapshot | undefined {
  if (!record(value) || !text(value.research_id, 128) || !Number.isSafeInteger(value.revision) ||
    Number(value.revision) < 1 || !boundedText(value.goal,'research_summary_chars') || !strings(value.condition_refs, applicationCapacity('context_references'), 256) ||
    !(Array.isArray(value.open_questions)&&!exceedsCapacity(value.open_questions.length,'research_question_count')&&value.open_questions.every(item=>boundedText(item,'research_text_chars'))) || !Array.isArray(value.claims) || exceedsCapacity(value.claims.length,'research_claim_count') ||
    !Array.isArray(value.notes) || exceedsCapacity(value.notes.length,'research_note_count')) return undefined
  if (!value.claims.every(item => record(item) && text(item.claim_id, 128) && boundedText(item.statement,'research_text_chars') &&
    ['pending', 'supported', 'refuted'].includes(String(item.status)) && strings(item.refs, applicationCapacity('context_references'), 256) &&
    (item.status === 'pending' || item.refs.length > 0))) return undefined
  if (!value.notes.every(item => record(item) && text(item.note_id, 128) && boundedText(item.text,'research_text_chars') && strings(item.refs, applicationCapacity('context_references'), 256))) return undefined
  return value as ResearchSnapshot
}

function Sources({ refs }: { refs: string[] }) {
  return refs.length > 0 ? <details className="capstone-evidence-trace"><summary>来源引用 · {refs.length} 条</summary>
    {refs.map(ref => <code key={ref}>{ref}</code>)}</details> : null
}
export default function ResearchEvidence({ snapshot }: { snapshot?: ResearchSnapshot }) {
  if (!snapshot) return null
  const notes = snapshot.notes.filter(item => !item.note_id.startsWith('runtime.checkpoint.'))
  return <details className="capstone-research-records"><summary>研究判断与工作记录 · 修订 {snapshot.revision}</summary>
    <p><strong>研究目标</strong>：{snapshot.goal}</p>
    <p>{snapshot.claims.length} 项判断 · {notes.length} 条工作记录 · {snapshot.open_questions.length} 个待解决问题</p>
    <p>以下为智能体已保存的研究记录。判断状态不等于独立计算核验通过。</p>
    {snapshot.claims.map(item => <section className="capstone-evidence-item" key={item.claim_id}>
      <strong>{item.status === 'pending' ? '待核验' : item.status === 'supported' ? '记录为有依据' : '记录为已否定'}</strong>
      <p>{item.statement}</p><Sources refs={item.refs} /></section>)}
    {notes.length > 0 && <strong>工作记录</strong>}
    {notes.map(item => <section key={item.note_id}><p>{item.text}</p><Sources refs={item.refs} /></section>)}
    {snapshot.open_questions.length > 0 && <><strong>待解决问题</strong><ul>{snapshot.open_questions.map((item, index) => <li key={index}>{item}</li>)}</ul></>}
    <Sources refs={snapshot.condition_refs} />
    <details className="capstone-evidence-trace"><summary>研究身份</summary><code>{snapshot.research_id}</code></details>
  </details>
}
