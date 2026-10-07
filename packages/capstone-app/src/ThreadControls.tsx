import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { ChevronDown, SlidersHorizontal } from 'lucide-react'
import ThreadSettingsMenu from './ThreadSettingsMenu'
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
  historyActions: ReactNode
  onProfileSelection: (profiles: ProfileReference[]) => void
}

export default function ThreadControls({ catalog, activeFamily, activeProfiles, pendingProfileSelection, pendingModel, disabled, historyActions, onProfileSelection }: ThreadControlsProps) {
  const compatibleProfiles = useMemo(
    () => (catalog?.profiles || []).filter((profile) => profile.implementationFamilies.includes(activeFamily)),
    [activeFamily, catalog?.profiles],
  )
  const selectedProfiles = pendingProfileSelection || activeProfiles
  const [draft, setDraft] = useState(selectedProfiles)
  const [open, setOpen] = useState(false)
  useEffect(() => setDraft(selectedProfiles), [pendingProfileSelection, activeProfiles])
  const changed = draft.map(profileKey).sort().join(',') !== selectedProfiles.map(profileKey).sort().join(',')

  function toggleProfile(profile: ThreadCatalogProfile): void {
    const reference = { profileId: profile.profileId, profileVersion: profile.profileVersion }
    const key = profileKey(reference)
    setDraft((current) => current.some((item) => profileKey(item) === key)
      ? current.filter((item) => profileKey(item) !== key)
      : [...current, reference])
  }

  return <div className="thread-compact-controls" aria-label="Thread 紧凑控制">
    <ThreadSettingsMenu>
      {historyActions}
      {compatibleProfiles.length > 0 && <details className="thread-settings-advanced">
        <summary>高级</summary>
        <details className="thread-profile-menu" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
          <summary className="thread-settings-item" role="button" aria-label="专业功能配置" title="专业功能配置"><SlidersHorizontal aria-hidden="true" /><span>专业功能配置</span><ChevronDown aria-hidden="true" /></summary>
          <div className="thread-profile-panel" role="group" aria-label="专业功能配置">
            <strong>{pendingProfileSelection ? '配置将在下条指令生效' : '可用分析功能'}</strong>
            <small>决定后续分析可使用的专业功能。已按模型配置，通常无需调整。</small>
            {compatibleProfiles.length === 0
              ? <small>当前模型没有可选专业功能</small>
              : compatibleProfiles.map((profile) => {
                const checked = draft.some((item) => item.profileId === profile.profileId && item.profileVersion === profile.profileVersion)
                return <label key={`${profile.profileId}@${profile.profileVersion}`} className="thread-profile-option"><input type="checkbox" aria-label={profile.displayName} checked={checked} disabled={disabled || Boolean(pendingModel)} onChange={() => toggleProfile(profile)} /><span>{profile.displayName}</span></label>
              })}
            <button type="button" className="thread-compact-apply" disabled={disabled || Boolean(pendingModel) || !changed} onClick={() => { onProfileSelection(draft); setOpen(false) }}>应用功能配置</button>
          </div>
        </details>
      </details>}
    </ThreadSettingsMenu>
    {pendingModel && <span className="thread-control-pending" role="status">模型切换待生效</span>}
  </div>
}
