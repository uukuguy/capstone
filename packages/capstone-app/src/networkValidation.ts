import type { NetworkView } from './types'

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function text(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0 && value.length <= 2048
}

function coordinate(value: unknown): boolean {
  return value === null || typeof value === 'number' && Number.isFinite(value)
}

export function parseNetworkView(raw: unknown, ordinal: number, admittedRefs: string[]): NetworkView | null {
  if (!record(raw) || raw.schema !== 'capstone-network-view/1.0' || raw.ordinal !== ordinal ||
      !record(raw.model) || !text(raw.model.id) || !text(raw.model.revision) || !text(raw.model.source) ||
      !['provided-unverified', 'schematic-required'].includes(String(raw.coordinate_status)) ||
      !Array.isArray(raw.buses) || raw.buses.length < 1 || raw.buses.length > 50 ||
      !Array.isArray(raw.branches) || raw.branches.length > 100 ||
      !record(raw.omitted) || !Number.isSafeInteger(raw.omitted.buses) || !Number.isSafeInteger(raw.omitted.branches) ||
      Number(raw.omitted.buses) < 0 || Number(raw.omitted.branches) < 0) return null

  const busIds = new Set<string>()
  for (const bus of raw.buses) {
    if (!record(bus) || !text(bus.id) || !text(bus.label) || !coordinate(bus.x) || !coordinate(bus.y) ||
        busIds.has(bus.id)) return null
    busIds.add(bus.id)
  }
  const branchIds = new Set<string>()
  const lineIds = new Set<string>()
  for (const branch of raw.branches) {
    if (!record(branch) || !text(branch.id) || !text(branch.label) ||
        !['line', 'link', 'transformer', 'trafo', 'trafo3w'].includes(String(branch.kind)) ||
        !busIds.has(String(branch.from_bus)) || !busIds.has(String(branch.to_bus)) ||
        busIds.has(branch.id) || branchIds.has(branch.id)) return null
    branchIds.add(branch.id)
    if (branch.kind === 'line') lineIds.add(branch.id)
  }
  const allIds = new Set([...busIds, ...branchIds])
  for (const key of ['focus_ids', 'next_focus_ids']) {
    const focus = raw[key]
    if (!Array.isArray(focus) || focus.length > 20 || new Set(focus).size !== focus.length ||
        focus.some((id) => !allIds.has(String(id)))) return null
  }
  if (raw.overlay !== null) {
    const overlay = raw.overlay
    if (!record(overlay) || !text(overlay.source_ref) || !admittedRefs.includes(overlay.source_ref) ||
        !Array.isArray(overlay.values) || overlay.values.length < 1 || overlay.values.length > 100 ||
        !((overlay.metric === 'loading_percent' && overlay.unit === '%') ||
          (overlay.metric === 'voltage_pu' && overlay.unit === 'p.u.'))) return null
    const allowed = overlay.metric === 'voltage_pu' ? busIds : lineIds
    const seen = new Set<string>()
    for (const item of overlay.values) {
      if (!record(item) || !text(item.id) || !allowed.has(item.id) || seen.has(item.id) ||
          typeof item.value !== 'number' || !Number.isFinite(item.value)) return null
      seen.add(item.id)
    }
  }
  return raw as NetworkView
}
