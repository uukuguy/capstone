import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode,type RefObject } from 'react'
import { useAui, useAuiState } from '@assistant-ui/react'
import { Brain, Sparkles } from 'lucide-react'
import { parseInputCommand, skillCompatible, inputDraftError, type InputCatalog, type InputDraft, type SkillChoice, type SkillRole } from './threadInput'
import ThreadContextPanel from './ThreadContextPanel'
import LlmProfileMenu from './LlmProfileMenu'

const commands = [{ text: '/skills', label: '查看已安装技能' }, { text: '/context', label: '查看与选择上下文' }]
const skillLabels: Record<string, {name: string; description: string}> = {
  'capstone-brainstorming': {name: '问题梳理', description: '澄清分析目标、范围与可行路径。'},
  'capstone-task-planning-and-tracking': {name: '任务规划与跟踪', description: '组织调查任务，跟踪进展和待解决问题。'},
  'capstone-systematic-debugging': {name: '系统排查', description: '围绕证据提出假设，逐步定位问题原因。'},
  'capstone-verification-before-completion': {name: '结论核验', description: '交付前核对结果、依据和未完成事项。'},
  'capstone-data-investigation': {name: '数据调查', description: '根据问题选择数据，组织有边界的调查分析。'},
  'capstone-data-quality-and-comparability': {name: '数据质量与可比性', description: '检查数据质量、口径、单位和时间范围是否可比较。'},
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
  const skills = allSkills.filter(skill => skill.installed === true).filter(skill => `${skillLabels[skill.id]?.name || ''} ${skill.id} ${skill.native_name || ''} ${skill.description || ''} ${skill.source}`.toLowerCase().includes(search.toLowerCase()))
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
  const inputTools = <div className="thread-input-tools">
      <button type="button" className="thread-settings-trigger" aria-label="技能" title="查看已安装技能" aria-expanded={panel==='skills'} onClick={()=>panel==='skills'?close():open('skills')}><Sparkles aria-hidden="true" size={16}/></button>
      <LlmProfileMenu catalog={catalog?.llm_profiles} value={draft.llm_profile_id} disabled={disabled||loading} onChange={id=>{if(onBeforeChange?.()!==false)onChange({...draft,llm_profile_id:id})}}/>

      {draft.mode==='capstone'&&<button disabled type="button" className="thread-settings-trigger thread-deep-research-toggle" aria-label="深度研究" aria-pressed={false} title="深度研究暂未开放"><Brain aria-hidden="true"/>深度研究</button>}
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
    {panel === 'skills' && <section role="dialog" aria-label="已安装技能" className="thread-settings-popover thread-input-panel">
      <div className="thread-input-heading"><strong>已安装技能</strong><button type="button" onClick={close}>关闭</button></div>
      <p>无需选择，应用会根据当前问题和上下文按需使用就绪技能。</p>
      <input aria-label="搜索技能" value={search} onChange={event => setSearch(event.target.value)} placeholder="搜索技能名称或用途" />
      {loading && <p role="status">正在读取已安装技能…</p>}
      {!loading && !skills.length && <p role="status">{search?'没有匹配的已安装技能。':'当前没有已安装技能。'}</p>}
      {skills.map(skill => <div className="thread-skill-entry" key={`${skill.role}:${skill.id}`}>
        <strong>{skillLabels[skill.id]?.name || skill.native_name || skill.id}</strong>
        <span className="thread-skill-summary">{skillLabels[skill.id]?.description || skill.description || '暂无用途说明。'}</span>
        <span>{skill.ready?'可用':'暂不可用'}</span>
        <details className="thread-skill-details"><summary>详情</summary>
          <dl><dt>标识</dt><dd>{skill.id}</dd><dt>版本</dt><dd>{skill.version}</dd><dt>来源</dt><dd>{skill.source}</dd></dl>
          {!skill.ready && <p>{skill.reason || '当前执行环境尚未就绪。'}</p>}
        </details>
      </div>)}
    </section>}
    {panel === 'context' && <ThreadContextPanel disabled={disabled} catalog={catalog} value={draft.context} materialRefs={draft.material_refs} onMaterialRefsChange={material_refs=>{if(onBeforeChange?.()!==false)onChange({...draft,material_refs})}} onRemoveMaterial={onRemoveMaterial} onChange={context => { if (onBeforeChange?.() !== false) onChange({ ...draft, context }) }} onClose={close} />}
    {panel === 'unknown' && <section role="dialog" aria-label="未知命令" className="thread-settings-popover thread-input-panel"><p>未识别此命令。可使用 /skills 或 /context，或按普通文本发送。</p><button disabled={disabled} type="button" onClick={() => { if (onBeforeChange?.() === false) return; onChange({ ...draft, literal: true, skill: undefined }); close() }}>按普通文本发送</button></section>}
    {typeof children === 'function' ? children(inputTools) : children}
  </div>
}
