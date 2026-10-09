import { describe, expect, it } from 'vitest'
import { parseInputCommand, buildInputSubmission, readInputDraft, writeInputDraft } from './threadInput'

describe('typed composer input', () => {
  it('parses only a leading standalone command position', () => {
    expect(parseInputCommand('/skills')).toEqual({ kind: 'skills', rest: '' })
    expect(parseInputCommand('/context task')).toEqual({ kind: 'context', rest: 'task' })
    expect(parseInputCommand('/skill:power-a explain')).toEqual({ kind: 'skill', name: 'power-a', rest: 'explain' })
    for (const text of ['/tmp/path', 'read /skills', '```\n/skills\n```', 'https://host/skills', ' /skills']) expect(parseInputCommand(text)).toBeNull()
    expect(parseInputCommand('/unknown')).toEqual({ kind: 'unknown', name: 'unknown', rest: '' })
  })
  it('retains resource identity, context choices and role through storage', () => {
    const state = { mode: 'capstone' as const, skill: { id: 'a', version: 'v1', role: 'delegated_pi' as const, revision: 'exact' },
      context: { include_refs: ['current'], exclude_refs: ['old'] }, literal: true }
    writeInputDraft('input-test', state)
    expect(readInputDraft('input-test')).toEqual(state)
    expect(buildInputSubmission(' task ', state)).toEqual({
      input: { kind: 'skill_invocation', text: ' task ', skill_id: 'a', skill_version: 'v1' },
      resource_profile: { profile_id: 'delegated_pi', revision: 'exact' }, context_selection: state.context,
    })
    expect(() => buildInputSubmission('task', { ...state, mode: 'pi_reference' })).toThrow(/重新选择/)
  })
})
