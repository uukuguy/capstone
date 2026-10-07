import { describe, expect, it } from 'vitest'
import { answerEvidenceState } from './threadEvidenceState'

describe('answer evidence action states', () => {
  it('uses admitted references, not answer text, to enable evidence', () => {
    expect(answerEvidenceState('completed', { mode: 'authority_backed', assurance: 'lineage_verified' }, ['evidence:1'])).toBe('available')
    expect(answerEvidenceState('completed', { mode: 'authority_backed', assurance: 'invented' }, ['evidence:1'])).toBe('unavailable')
    expect(answerEvidenceState('completed', undefined, ['evidence:1'])).toBe('unavailable')
  })
  it('distinguishes information answers, missing required evidence and failed projection', () => {
    expect(answerEvidenceState('completed', { mode: 'offline_information', assurance: 'general_knowledge' }, [])).toBe('not_applicable')
    expect(answerEvidenceState('completed', undefined, [])).toBe('not_applicable')
    expect(answerEvidenceState('completed', { mode: 'authority_backed', assurance: 'lineage_verified' }, [])).toBe('missing')
    expect(answerEvidenceState('failed', undefined, [], 'capability_required')).toBe('missing')
    expect(answerEvidenceState('failed', undefined, [], 'answer_admission_failed')).toBe('unavailable')
    expect(answerEvidenceState('completed', { mode: 'limited', assurance: 'limited' }, [])).toBe('unavailable')
  })
  it('keeps unfinished attempts pending and never enables stale references', () => {
    expect(answerEvidenceState('running', { mode: 'authority_backed', assurance: 'lineage_verified' }, ['evidence:1'])).toBe('pending')
    expect(answerEvidenceState('cancelled', { mode: 'authority_backed', assurance: 'lineage_verified' }, ['evidence:1'])).toBe('unavailable')
    expect(answerEvidenceState('completed', { mode: 'offline_information', assurance: 'general_knowledge' }, ['evidence:1'])).toBe('unavailable')
  })
})
