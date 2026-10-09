import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useAui, useAuiState } from '@assistant-ui/react'
import { BookOpen, Layers, X } from 'lucide-react'
import { parseInputCommand, skillCompatible, inputDraftError, type InputCatalog, type InputDraft, type SkillChoice, type SkillRole } from './threadInput'
import ThreadContextPanel from './ThreadContextPanel'

const commands = [{ text: '/skills', label: '选择本轮技能' }, { text: '/context', label: '查看与选择上下文' }]
export default function ThreadCommandMenu({ children, catalog, loading, onRefresh, draft, onChange }: {
  children: ReactNode; catalog?: InputCatalog; loading?: boolean; onRefresh?: () => void; draft: InputDraft; onChange: (value: InputDraft) => void
}) {
  const aui = useAui()
  const text = useAuiState(state => state.composer.text)
  const [panel, setPanel] = useState<'skills' | 'context' | 'unknown' | null>(null)
  const [dismissed, setDismissed] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [index, setIndex] = useState(0)
  const root = useRef<HTMLDivElement>(null)
  const composing = useRef(false)
  const candidates = text.startsWith('/') && /^\/[a-z]*$/.test(text) && text !== dismissed && !panel
    ? commands.filter(item => item.text.startsWith(text)) : []
  const allSkills = Object.entries(catalog?.resource_profiles || {}).flatMap(([role, profile]) => profile!.resources
    .filter(resource => resource.kind === 'skill' && skillCompatible({ role } as SkillChoice, draft.mode))
    .map(resource => ({ ...resource, role: role as SkillRole, revision: profile!.revision })))
  const skills = allSkills.filter(skill => `${skill.id} ${skill.source}`.toLowerCase().includes(search.toLowerCase()))
  const focus = () => root.current?.querySelector<HTMLTextAreaElement>('textarea')?.focus({ preventScroll: true })
  function close() { setPanel(null); setDismissed(text); focus() }
  function open(value: 'skills' | 'context') { setPanel(value); setSearch(''); onRefresh?.() }
  function select(skill: typeof allSkills[number], rest?: string) {
    onChange({ ...draft, literal: false, skill: { id: skill.id, version: skill.version, role: skill.role, revision: skill.revision } })
    if (rest !== undefined) aui.composer.setText(rest)
    close()
  }
  function consumeCommand(): boolean {
    if (draft.literal) return false
    const command = parseInputCommand(text)
    if (!command) return false
    if (command.kind === 'skills' || command.kind === 'context') { aui.composer.setText(command.rest); open(command.kind); return true }
    if (command.kind === 'skill') {
      const matching = allSkills.filter(skill => skill.id === command.name && skill.ready)
      if (matching.length === 1) select(matching[0], command.rest)
      else { open('skills'); setSearch(command.name) }
      return true
    }
    setPanel('unknown'); return true
  }
  useEffect(() => {
    if (!panel && !candidates.length) return
    const outside = (event: PointerEvent) => { if (event.target instanceof Node && !root.current?.contains(event.target)) { setPanel(null); setDismissed(text) } }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [panel, candidates.length, text])
  const draftError = inputDraftError(draft, catalog)
  return <div ref={root} className="thread-input-controls" onCompositionStart={() => { composing.current = true }} onCompositionEnd={() => { composing.current = false }}
    onClickCapture={event => {
      if (event.target instanceof Element && event.target.closest('.capstone-chat-send') && (composing.current || consumeCommand())) { event.preventDefault(); event.stopPropagation() }
    }}
    onSubmitCapture={event => { if (composing.current || consumeCommand()) { event.preventDefault(); event.stopPropagation() } }}
    onKeyDownCapture={event => {
      if (composing.current || event.nativeEvent.isComposing || event.keyCode === 229) {
        if (event.key === 'Enter') { event.preventDefault(); event.stopPropagation() }
        return
      }
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); return }
      if (!(event.target instanceof HTMLTextAreaElement)) return
      if (candidates.length && ['ArrowDown', 'ArrowUp', 'Tab', 'Enter'].includes(event.key)) {
        event.preventDefault(); event.stopPropagation()
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') setIndex((index + (event.key === 'ArrowDown' ? 1 : -1) + candidates.length) % candidates.length)
        else {
          const command = candidates[index % candidates.length].text
          aui.composer.setText(''); open(command === '/skills' ? 'skills' : 'context')
        }
      } else if (event.key === 'Enter' && !event.shiftKey && consumeCommand()) { event.preventDefault(); event.stopPropagation() }
    }}>
    <div className="thread-input-tools">
      <button type="button" className="thread-settings-trigger" aria-label="选择技能" aria-expanded={panel === 'skills'} onClick={() => panel === 'skills' ? close() : open('skills')}><BookOpen aria-hidden="true" />技能</button>
      <button type="button" className="thread-settings-trigger" aria-label="本轮上下文" aria-expanded={panel === 'context'} onClick={() => panel === 'context' ? close() : open('context')}><Layers aria-hidden="true" />上下文</button>
      {draft.skill && <button type="button" className="thread-input-chip" aria-label={`移除技能 ${draft.skill.id}`} onClick={() => onChange({ ...draft, skill: undefined })}>{draft.skill.id}<X aria-hidden="true" /></button>}
    </div>
    {draftError && <p className="thread-input-warning" role="alert">{draftError}</p>}
    {candidates.length > 0 && <div role="listbox" aria-label="输入命令" className="thread-settings-popover thread-input-panel">{candidates.map((item, i) => <button type="button" role="option" aria-selected={i === index % candidates.length} key={item.text} onClick={() => { aui.composer.setText(''); open(item.text === '/skills' ? 'skills' : 'context') }}>{item.text}<span>{item.label}</span></button>)}</div>}
    {panel === 'skills' && <section role="dialog" aria-label="本轮技能" className="thread-settings-popover thread-input-panel">
      <div className="thread-input-heading"><strong>本轮技能</strong><button type="button" onClick={close}>关闭</button></div>
      <input aria-label="搜索技能" value={search} onChange={event => setSearch(event.target.value)} placeholder="搜索技能名称或来源" />
      {loading && <p role="status">正在读取可用技能…</p>}
      {!loading && !skills.length && <p role="status">当前没有可用技能。可稍后重新打开目录。</p>}
      {skills.map(skill => <button type="button" className="thread-input-skill" key={`${skill.role}:${skill.id}`} disabled={!skill.ready} onClick={() => select(skill, parseInputCommand(text)?.kind === 'skill' ? parseInputCommand(text)!.rest : undefined)}>
        <span>{skill.id} · {skill.role === 'delegated_pi' ? '委托 Pi' : skill.role === 'direct_pi' ? 'Pi' : 'Capstone 专业适配'}</span><small>{skill.ready ? skill.source : skill.reason || '暂不可用'}</small>
      </button>)}
    </section>}
    {panel === 'context' && <ThreadContextPanel catalog={catalog} value={draft.context} onChange={context => onChange({ ...draft, context })} onClose={close} />}
    {panel === 'unknown' && <section role="dialog" aria-label="未知命令" className="thread-settings-popover thread-input-panel"><p>未识别此命令。可使用 /skills 或 /context，或按普通文本发送。</p><button type="button" onClick={() => { onChange({ ...draft, literal: true, skill: undefined }); close() }}>按普通文本发送</button></section>}
    {children}
  </div>
}
