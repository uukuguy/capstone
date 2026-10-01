import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, ChevronDown, ListTree, Settings2, SlidersHorizontal } from 'lucide-react'
import type { ThreadCatalog, ThreadCatalogProfile } from './threadCatalog'
import type { ProfileReference } from './threadProtocol'

function profileKey(profile: ProfileReference): string {
  return `${profile.profileId}@${profile.profileVersion}`
}

export type ThreadControlsProps = {
  catalog: ThreadCatalog | null
  activeFamily: string
  activeProfiles: ProfileReference[]
  pendingProfileSelection: ProfileReference[] | undefined
  pendingModel: string | undefined
  disabled: boolean
  traceVisible: boolean
  onTraceToggle: () => void
  onProfileSelection: (profiles: ProfileReference[]) => void
}

export default function ThreadControls({ catalog, activeFamily, activeProfiles, pendingProfileSelection, pendingModel, disabled, traceVisible, onTraceToggle, onProfileSelection }: ThreadControlsProps) {
  const compatibleProfiles = useMemo(
    () => (catalog?.profiles || []).filter((profile) => profile.implementationFamilies.includes(activeFamily)),
    [activeFamily, catalog?.profiles],
  )
  const selectedProfiles = pendingProfileSelection || activeProfiles
  const settingsRef = useRef<HTMLDetailsElement>(null)
  const [draft, setDraft] = useState(selectedProfiles)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [open, setOpen] = useState(false)
  useEffect(() => setDraft(selectedProfiles), [pendingProfileSelection, activeProfiles])
  useEffect(() => {
    const closeOnOutsideClick = (event: MouseEvent) => {
      const target = event.target
      if (settingsRef.current?.open && target instanceof Node && !settingsRef.current.contains(target)) {
        settingsRef.current.removeAttribute('open')
        setSettingsOpen(false)
        setOpen(false)
      }
    }
    document.addEventListener('click', closeOnOutsideClick, true)
    return () => document.removeEventListener('click', closeOnOutsideClick, true)
  }, [])

  function toggleProfile(profile: ThreadCatalogProfile): void {
    const reference = { profileId: profile.profileId, profileVersion: profile.profileVersion }
    const key = profileKey(reference)
    setDraft((current) => current.some((item) => profileKey(item) === key)
      ? current.filter((item) => profileKey(item) !== key)
      : [...current, reference])
  }

  return <div className="thread-compact-controls" aria-label="Thread 紧凑控制">
    <details ref={settingsRef} className="thread-settings-menu" open={settingsOpen} onToggle={(event) => setSettingsOpen(event.currentTarget.open)}>
      <summary className="thread-settings-trigger" role="button" aria-label="输入设置" title="输入设置"><Settings2 aria-hidden="true" /><span>设置</span><ChevronDown aria-hidden="true" /></summary>
      <div className="thread-settings-popover" role="group" aria-label="输入设置">
        <div className="thread-routing-status"><span className="thread-routing-dot" aria-hidden="true" /><div><strong>自动路由</strong><small>按指令自动选择对话或专业分析</small></div></div>
        <details className="thread-profile-menu" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
          <summary className="thread-settings-item" role="button" aria-label="选择 Profile" title="选择 Profile"><SlidersHorizontal aria-hidden="true" /><span>Profile</span><ChevronDown aria-hidden="true" /></summary>
          <div className="thread-profile-panel" role="group" aria-label="Profile 选择">
            <strong>{pendingProfileSelection ? 'Profile 将在下一 Turn 生效' : `${activeFamily} Profile`}</strong>
            {compatibleProfiles.length === 0
              ? <small>当前模型没有可用 Profile</small>
              : compatibleProfiles.map((profile) => {
                const checked = draft.some((item) => item.profileId === profile.profileId && item.profileVersion === profile.profileVersion)
                return <label key={`${profile.profileId}@${profile.profileVersion}`} className="thread-profile-option"><input type="checkbox" aria-label={profile.displayName} checked={checked} disabled={disabled || Boolean(pendingModel)} onChange={() => toggleProfile(profile)} /><span>{profile.displayName}</span><small>{profile.profileId} · {profile.profileVersion}</small></label>
              })}
            <button type="button" className="thread-compact-apply" disabled={disabled || Boolean(pendingModel) || compatibleProfiles.length === 0} onClick={() => { onProfileSelection(draft); setOpen(false) }}>应用 Profile 选择</button>
          </div>
        </details>
        <button type="button" className={`thread-settings-item thread-trace-item${traceVisible ? ' is-active' : ''}`} aria-label={traceVisible ? '隐藏运行过程' : '显示运行过程'} title={traceVisible ? '隐藏运行过程' : '显示运行过程'} onClick={onTraceToggle}><ListTree aria-hidden="true" /><span>显示运行过程</span>{traceVisible && <Check aria-hidden="true" />}</button>
      </div>
    </details>
    {pendingModel && <span className="thread-control-pending" role="status">模型切换待生效</span>}
  </div>
}
