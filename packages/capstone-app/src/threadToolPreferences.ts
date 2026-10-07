import type { ThreadCatalogProfile } from './threadCatalog'
import type { ProfileReference } from './threadProtocol'

// Application preferences use stable group IDs. Runtime selection uses exact
// registered versions and a model-compatible subset of those preferences.
export function enabledTools(profiles: ThreadCatalogProfile[], disabledIds: readonly string[]): ThreadCatalogProfile[] {
  return profiles.filter((profile) => !disabledIds.includes(profile.profileId))
}

export function effectiveTools(profiles: ThreadCatalogProfile[], disabledIds: readonly string[], family: string): ThreadCatalogProfile[] {
  return enabledTools(profiles, disabledIds).filter((profile) => profile.implementationFamilies.includes(family))
}

export function updateToolPreferences(profiles: ThreadCatalogProfile[], disabledIds: readonly string[], selection: ProfileReference[]): string[] {
  const registered = new Set(profiles.map((profile) => profile.profileId))
  const enabled = new Set(selection.map((profile) => profile.profileId))
  return [...disabledIds.filter((id) => !registered.has(id)), ...profiles.filter((profile) => !enabled.has(profile.profileId)).map((profile) => profile.profileId)]
}
