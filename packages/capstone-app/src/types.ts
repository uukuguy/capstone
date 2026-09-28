export type CaseCard = {
  case_id: string
  title: string
  summary: string
  model_origin: string
  scenario_assumption: string
  interpretation_boundary: string
  instructions: string[]
}

export type ApplicationCard = {
  application_id: string
  title: string
  cases: CaseCard[]
}

export type Catalog = {
  schema: 'capstone-catalog/1.0'
  applications: ApplicationCard[]
}

export type SessionState = 'pending' | 'ready' | 'executing' | 'closing' |
  'completed' | 'failed' | 'interrupted'

export type SessionStatus = {
  session_id: string
  run_id: string | null
  application_id: string
  state: SessionState
  error_code: string | null
  accepted_turns: number
  completed_turns: number
}

export type CreatedSession = {
  session_id: string
  run_id: string | null
  application_id: string
  state: SessionState
}

export type CommittedTurn = {
  ordinal: number
  turn_id: string
  answer_output: string
  answer_summary?: string
  answer_ref: string
  result_refs: string[]
  evidence_refs: string[]
  duration_ms?: number
}

export type SessionEvent = {
  schema: 'capstone-session-event/1.0'
  session_id: string
  sequence: number
  event: string
  payload: Record<string, unknown>
}

export type LegacyNetworkView = {
  schema: 'capstone-network-view/1.0'
  ordinal: number
  model: { id: string; revision: string; source: string }
  coordinate_status: 'provided-unverified' | 'schematic-required'
  buses: { id: string; label: string; x: number | null; y: number | null }[]
  branches: { id: string; kind: 'line' | 'link' | 'transformer' | 'trafo' | 'trafo3w';
    label: string; from_bus: string; to_bus: string }[]
  omitted: { buses: number; branches: number }
  focus_ids: string[]
  next_focus_ids: string[]
  overlay: null | {
    metric: 'loading_percent' | 'voltage_pu'
    unit: '%' | 'p.u.'
    source_ref: string
    values: { id: string; value: number }[]
  }
}

export type NetworkDiagram = {
  schema: 'capstone-network-diagram/1.0'
  model: { id: string; revision: string; source: string }
  coordinate_system: 'geographic' | 'schematic'
  buses: { id: string; label: string; x: number | null; y: number | null; vn_kv: number | null }[]
  branches: { id: string; kind: 'line' | 'link' | 'transformer' | 'trafo' | 'trafo3w';
    label: string; from_bus: string; to_bus: string }[]
  fingerprint: string
  ref: string
}

export type NetworkLayer = {
  schema: 'capstone-network-layer/1.0'
  ordinal: number
  diagram_ref: string
  model_revision: string
  focus_ids: string[]
  next_focus_ids: string[]
  overlay: LegacyNetworkView['overlay']
}

export type DiagramNetworkView = {
  schema: 'capstone-network-view/2.0'
  ordinal: number
  diagram: NetworkDiagram
  layer: NetworkLayer
}

export type NetworkView = LegacyNetworkView | DiagramNetworkView

export type NetworkStoryStep = {
  schema: 'capstone-network-story-step/1.0'
  ordinal: number
  diagram_ref: string
  model_revision: string
  current_focus_ids: string[]
  history_focus_ids: string[]
  overlay: LegacyNetworkView['overlay']
  plan_source: 'llm' | 'fallback'
}

export type NetworkStory = {
  schema: 'capstone-network-story/1.0'
  mode: 'cumulative-snapshots'
  story_status: 'complete' | 'partial'
  plan_source: 'llm' | 'fallback'
  diagram: NetworkDiagram
  steps: NetworkStoryStep[]
}
