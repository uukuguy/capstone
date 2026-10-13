type Claim = { claim_id: string; statement: string; status: 'pending' | 'supported' | 'refuted'; refs: string[] }
type Note = { note_id: string; text: string; refs: string[] }
export type ResearchSnapshot = { research_id: string; revision: number; goal: string;
  condition_refs: string[]; claims: Claim[]; notes: Note[]; open_questions: string[] }
const text = (value: unknown, max: number): value is string => typeof value === 'string' && value.length > 0 && value.length <= max
const strings = (value: unknown, count: number, length: number): value is string[] =>
  Array.isArray(value) && value.length <= count && value.every(item => text(item, length))
const record = (value: unknown): value is Record<string, unknown> => Boolean(value && typeof value === 'object' && !Array.isArray(value))

export function parseResearchSnapshot(value: unknown): ResearchSnapshot | undefined {
  if (!record(value) || !text(value.research_id, 128) || !Number.isSafeInteger(value.revision) ||
    Number(value.revision) < 1 || !text(value.goal, 4000) || !strings(value.condition_refs, 32, 256) ||
    !strings(value.open_questions, 32, 2000) || !Array.isArray(value.claims) || value.claims.length > 64 ||
    !Array.isArray(value.notes) || value.notes.length > 64) return undefined
  if (!value.claims.every(item => record(item) && text(item.claim_id, 128) && text(item.statement, 2000) &&
    ['pending', 'supported', 'refuted'].includes(String(item.status)) && strings(item.refs, 32, 256) &&
    (item.status === 'pending' || item.refs.length > 0))) return undefined
  if (!value.notes.every(item => record(item) && text(item.note_id, 128) && text(item.text, 2000) && strings(item.refs, 32, 256))) return undefined
  return value as ResearchSnapshot
}

function Sources({ refs }: { refs: string[] }) {
  return refs.length > 0 ? <details className="capstone-evidence-trace"><summary>来源引用 · {refs.length} 条</summary>
    {refs.map(ref => <code key={ref}>{ref}</code>)}</details> : null
}
export default function ResearchEvidence({ snapshot }: { snapshot?: ResearchSnapshot }) {
  if (!snapshot) return null
  return <details className="capstone-research-records"><summary>研究判断与工作记录 · 修订 {snapshot.revision}</summary>
    <p><strong>研究目标</strong>：{snapshot.goal}</p>
    <p>{snapshot.claims.length} 项判断 · {snapshot.notes.length} 条工作记录 · {snapshot.open_questions.length} 个待解决问题</p>
    <p>以下为智能体已保存的研究记录。判断状态不等于独立计算核验通过。</p>
    {snapshot.claims.map(item => <section className="capstone-evidence-item" key={item.claim_id}>
      <strong>{item.status === 'pending' ? '待核验' : item.status === 'supported' ? '记录为有依据' : '记录为已否定'}</strong>
      <p>{item.statement}</p><Sources refs={item.refs} /></section>)}
    {snapshot.notes.length > 0 && <strong>工作记录</strong>}
    {snapshot.notes.map(item => <section key={item.note_id}><p>{item.text}</p><Sources refs={item.refs} /></section>)}
    {snapshot.open_questions.length > 0 && <><strong>待解决问题</strong><ul>{snapshot.open_questions.map((item, index) => <li key={index}>{item}</li>)}</ul></>}
    <Sources refs={snapshot.condition_refs} />
    <details className="capstone-evidence-trace"><summary>研究身份</summary><code>{snapshot.research_id}</code></details>
  </details>
}
