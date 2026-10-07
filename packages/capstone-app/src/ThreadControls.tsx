import { useEffect, useState, type ReactNode } from 'react'
import ThreadSettingsMenu, { useCloseThreadSettings } from './ThreadSettingsMenu'
import type { ThreadCatalog, ThreadCatalogProfile } from './threadCatalog'
import type { ProfileReference } from './threadProtocol'

function profileKey(profile: ProfileReference): string {
  return `${profile.profileId}@${profile.profileVersion}`
}

export type ThreadControlsProps = {
  catalog: ThreadCatalog | null
  selectedProfiles: ProfileReference[]
  pendingModel: string | undefined
  disabled: boolean
  historyActions: ReactNode
  onProfileSelection: (profiles: ProfileReference[]) => void
}

function toolName(profile: ThreadCatalogProfile): string {
  if (profile.profileId === 'pandapower-static-analysis') return 'pandapower 静态分析'
  if (profile.profileId === 'pypsa-business-cases') return 'PyPSA 电网分析'
  return profile.displayName
}

function GridToolSelection({ profiles, selectedProfiles, disabled, onSave }: {
  profiles: ThreadCatalogProfile[]; selectedProfiles: ProfileReference[];
  disabled: boolean; onSave: (profiles: ProfileReference[]) => void
}) {
  const [draft, setDraft] = useState(selectedProfiles)
  const close = useCloseThreadSettings()
  useEffect(() => setDraft(selectedProfiles), [selectedProfiles])
  const changed = draft.map(profileKey).sort().join(',') !== selectedProfiles.map(profileKey).sort().join(',')

  function toggleProfile(profile: ThreadCatalogProfile): void {
    const reference = { profileId: profile.profileId, profileVersion: profile.profileVersion }
    const key = profileKey(reference)
    setDraft((current) => current.some((item) => profileKey(item) === key)
      ? current.filter((item) => profileKey(item) !== key)
      : [...current, reference])
  }

  return <div className="thread-grid-tools" role="group" aria-label="电网计算分析工具">
    <div className="thread-grid-tools-heading"><span className="thread-settings-section">电网计算分析工具</span>
      {changed && <button type="button" className="thread-tool-save" aria-label="保存工具选择" disabled={disabled} onClick={() => { onSave(draft); close() }}>保存</button>}
    </div>
    {profiles.map((profile) => {
      return <label key={profileKey(profile)} className="thread-profile-option">
        <input type="checkbox" aria-label={toolName(profile)} checked={draft.some((item) => profileKey(item) === profileKey(profile))} disabled={disabled} onChange={() => toggleProfile(profile)} />
        <span>{toolName(profile)}</span>
      </label>
    })}
  </div>
}

export default function ThreadControls({ catalog, selectedProfiles, pendingModel, disabled, historyActions, onProfileSelection }: ThreadControlsProps) {
  const profiles = catalog?.profiles || []
  return <div className="thread-compact-controls" aria-label="Thread 紧凑控制">
    <ThreadSettingsMenu>
      {historyActions}
      {profiles.length > 0 && <GridToolSelection profiles={profiles} selectedProfiles={selectedProfiles}
        disabled={disabled} onSave={onProfileSelection} />}
    </ThreadSettingsMenu>
    {pendingModel && <span className="thread-control-pending" role="status">模型切换待生效</span>}
  </div>
}
