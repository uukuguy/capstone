import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode,type RefObject } from 'react'
import { useAui, useAuiState } from '@assistant-ui/react'
import { Brain, X } from 'lucide-react'
import { parseInputCommand, skillCompatible, inputDraftError, type InputCatalog, type InputDraft, type SkillChoice, type SkillRole } from './threadInput'
import ThreadContextPanel from './ThreadContextPanel'

const commands = [{ text: '/skills', label: '选择本轮技能' }, { text: '/context', label: '查看与选择上下文' }]
const skillLabels: Record<string, {name: string; description: string}> = {
  'anthropic-explore-data': {name: '数据体检', description: '检查数据结构、缺失、重复和分布，提出后续分析建议。'},
  'powerskills-pandapower': {name: '电网分析', description: '辅助检查电网模型、潮流结果与运行约束。'},
}
export default function ThreadCommandMenu({ children, catalog, loading, onRefresh, draft, onChange, disabled, onBeforeChange,contextTriggerRef,onRemoveMaterial }: {
  children: ReactNode | ((tools: ReactNode) => ReactNode); catalog?: InputCatalog; loading?: boolean; onRefresh?: () => void; draft: InputDraft; onChange: (value: InputDraft) => void; disabled?: boolean; onBeforeChange?: () => boolean
  contextTriggerRef?:RefObject<HTMLButtonElement|null>;onRemoveMaterial?:(id:string)=>Promise<void>
}) {
  const aui = useAui()
  const text = useAuiState(state => state.composer.text)
  const [panel, setPanel] = useState<'skills' | 'context' | 'unknown' | null>(null)
  const [dismissed, setDismissed] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [index, setIndex] = useState(0)
  const [panelHeight, setPanelHeight] = useState<number>()
  const root = useRef<HTMLDivElement>(null)
  const composing = useRef(false)
  const candidates = !disabled && text.startsWith('/') && /^\/[a-z]*$/.test(text) && text !== dismissed && !panel
    ? commands.filter(item => item.text.startsWith(text)) : []
  const allSkills = Object.entries(catalog?.resource_profiles || {}).flatMap(([role, profile]) => profile!.resources
    .filter(resource => resource.kind === 'skill' && skillCompatible({ role } as SkillChoice, draft.mode))
    .map(resource => ({ ...resource, role: role as SkillRole, revision: profile!.revision })))
  const skills = allSkills.filter(skill => `${skillLabels[skill.id]?.name || ''} ${skill.id} ${skill.native_name || ''} ${skill.description || ''} ${skill.source}`.toLowerCase().includes(search.toLowerCase()))
  const panelVisible = Boolean(panel || candidates.length)
  useLayoutEffect(() => {
    if (!panelVisible || !root.current) return
    const controls = root.current
    const boundaries = [controls.closest('.capstone-assistant-thread'), controls.closest('.thread-chat-pane')]
      .filter((element): element is Element => element !== null)
    const measure = () => {
      // The panel opens above the controls, inside the thread's clipping bounds.
      const top = Math.max(8, ...boundaries.map(element => element.getBoundingClientRect().top + 8))
      setPanelHeight(Math.max(0, controls.getBoundingClientRect().top - top - 8))
    }
    measure()
    const observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(measure)
    observer?.observe(controls)
    boundaries.forEach(element => observer?.observe(element))
    window.addEventListener('resize', measure)
    document.addEventListener('scroll', measure, true)
    return () => {
      observer?.disconnect()
      window.removeEventListener('resize', measure)
      document.removeEventListener('scroll', measure, true)
    }
  }, [panelVisible])
  const focus = () => root.current?.querySelector<HTMLTextAreaElement>('textarea')?.focus({ preventScroll: true })
  function close() { setPanel(null); setDismissed(text); focus() }
  function open(value: 'skills' | 'context') { setPanel(value); setSearch(''); onRefresh?.() }
  function select(skill: typeof allSkills[number], rest?: string) {
    if (disabled || onBeforeChange?.() === false) return
    onChange({ ...draft, literal: false, skill: { id: skill.id, version: skill.version, role: skill.role, revision: skill.revision } })
    if (rest !== undefined) aui.composer.setText(rest)
    close()
  }
  function consumeCommand(): boolean {
    if (draft.literal) return false
    const command = parseInputCommand(text)
    if (!command) return false
    if (disabled) return true
    if (command.kind === 'skills' || command.kind === 'context') { aui.composer.setText(command.rest); open(command.kind); return true }
    if (command.kind === 'skill') {
      const byId = allSkills.filter(skill => skill.id === command.name)
      const matching = byId.length ? byId : allSkills.filter(skill => skill.native_name === command.name)
      if (matching.length === 1 && matching[0].ready) select(matching[0], command.rest)
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
  const selectedSkillName = allSkills.find(skill => skill.id === draft.skill?.id)?.native_name || draft.skill?.id
  const inputTools = <div className="thread-input-tools">
      {draft.mode==='capstone'&&<button disabled={disabled} type="button" className="thread-settings-trigger thread-deep-research-toggle" aria-label="深度思考" aria-pressed={draft.deep_research===true} title={draft.deep_research?'本条指令使用 Deep Research 任务组织；发送后恢复关闭':'开启后，本条指令使用 Deep Research 任务组织'} onClick={()=>{if(onBeforeChange?.()!==false)onChange({...draft,deep_research:!draft.deep_research})}}><Brain aria-hidden="true"/>深度思考</button>}
    </div>
  return <div ref={root} className="thread-input-controls" style={panelHeight === undefined ? undefined : { '--thread-input-panel-space': `${panelHeight}px` } as CSSProperties} onCompositionStart={() => { composing.current = true }} onCompositionEnd={() => { composing.current = false }}
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
      if (disabled && event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.stopPropagation(); return }
      if (candidates.length && ['ArrowDown', 'ArrowUp', 'Tab', 'Enter'].includes(event.key)) {
        event.preventDefault(); event.stopPropagation()
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') setIndex((index + (event.key === 'ArrowDown' ? 1 : -1) + candidates.length) % candidates.length)
        else {
          const command = candidates[index % candidates.length].text
          aui.composer.setText(''); open(command === '/skills' ? 'skills' : 'context')
        }
      } else if (event.key === 'Enter' && !event.shiftKey && consumeCommand()) { event.preventDefault(); event.stopPropagation() }
    }}>
    {typeof children !== 'function' && inputTools}
    {draftError && <p className="thread-input-warning" role="alert">{draftError}</p>}
    {candidates.length > 0 && <div role="listbox" aria-label="输入命令" className="thread-settings-popover thread-input-panel">{candidates.map((item, i) => <button type="button" role="option" aria-selected={i === index % candidates.length} key={item.text} onClick={() => { aui.composer.setText(''); open(item.text === '/skills' ? 'skills' : 'context') }}>{item.text}<span>{item.label}</span></button>)}</div>}
    {panel === 'skills' && <section role="dialog" aria-label="本轮技能" className="thread-settings-popover thread-input-panel">
      <div className="thread-input-heading"><strong>本轮技能</strong><button type="button" onClick={close}>关闭</button></div>
      {draft.skill && <div className="thread-skill-selection">已选：{selectedSkillName}<button disabled={disabled} type="button" aria-label={`移除技能 ${draft.skill.id}`} onClick={() => { if (onBeforeChange?.() !== false) onChange({ ...draft, skill: undefined }) }}><X aria-hidden="true" />移除</button></div>}
      <input aria-label="搜索技能" value={search} onChange={event => setSearch(event.target.value)} placeholder="搜索技能名称或来源" />
      {loading && <p role="status">正在读取可用技能…</p>}
      {!loading && !skills.length && <p role="status">当前没有可用技能。可稍后重新打开目录。</p>}
      {skills.map(skill => <div className="thread-skill-entry" key={`${skill.role}:${skill.id}`}>
        <button type="button" className="thread-input-skill" disabled={disabled || !skill.ready} onClick={() => select(skill, parseInputCommand(text)?.kind === 'skill' ? parseInputCommand(text)!.rest : undefined)}>
          <strong>{skill.native_name || skill.id}</strong>
          <span className="thread-skill-summary">{skill.ready ? skillLabels[skill.id]?.description || skill.description || '选择后用于本轮任务。' : '暂不可用，请查看详情。'}</span>
        </button>
        <details className="thread-skill-details"><summary>详情</summary>
          <p>{skill.description}</p>
          <dl><dt>标识</dt><dd>{skill.id}</dd><dt>版本</dt><dd>{skill.version}</dd><dt>来源</dt><dd>{skill.source}</dd></dl>
          {!skill.ready && <p>{skill.reason || '当前执行环境尚未就绪。'}</p>}
        </details>
      </div>)}
      <p className="thread-skill-install-note">由管理员安装和更新；这里选择本轮使用的技能。</p>
    </section>}
    {panel === 'context' && <ThreadContextPanel disabled={disabled} catalog={catalog} value={draft.context} materialRefs={draft.material_refs} onMaterialRefsChange={material_refs=>{if(onBeforeChange?.()!==false)onChange({...draft,material_refs})}} onRemoveMaterial={onRemoveMaterial} onChange={context => { if (onBeforeChange?.() !== false) onChange({ ...draft, context }) }} onClose={close} />}
    {panel === 'unknown' && <section role="dialog" aria-label="未知命令" className="thread-settings-popover thread-input-panel"><p>未识别此命令。可使用 /skills 或 /context，或按普通文本发送。</p><button disabled={disabled} type="button" onClick={() => { if (onBeforeChange?.() === false) return; onChange({ ...draft, literal: true, skill: undefined }); close() }}>按普通文本发送</button></section>}
    {typeof children === 'function' ? children(inputTools) : children}
  </div>
}
