export type AnswerEvidenceState = 'available' | 'not_applicable' | 'missing' | 'pending' | 'unavailable'

export const evidenceStateCopy: Record<AnswerEvidenceState, string> = {
  available: '查看证据',
  not_applicable: '普通信息回答无需运行证据',
  missing: '缺少所需证据',
  pending: '证据同步中',
  unavailable: '证据暂不可用',
}

/** Read structured Attempt state and admission. Never inspect answer prose. */
export function answerEvidenceState(phase: string | undefined, admission: unknown, refs: readonly string[], errorCode?: string): AnswerEvidenceState {
  if (['running', 'waiting', 'committing', 'accepted', 'created'].includes(phase || '')) return 'pending'
  if (phase !== 'completed') return errorCode === 'capability_required' ? 'missing' : 'unavailable'
  if (admission === undefined || admission === null) return refs.length ? 'unavailable' : 'not_applicable'
  if (typeof admission !== 'object' || Array.isArray(admission)) return 'unavailable'
  const decision = admission as Record<string, unknown>
  if (decision.mode === 'offline_information' &&
      ['deterministic_information', 'guide_access_verified', 'general_knowledge'].includes(String(decision.assurance))) {
    return refs.length ? 'unavailable' : 'not_applicable'
  }
  if ((decision.mode === 'authority_backed' && decision.assurance === 'lineage_verified') || decision.status === 'admitted') {
    return refs.length ? 'available' : 'missing'
  }
  return 'unavailable'
}
