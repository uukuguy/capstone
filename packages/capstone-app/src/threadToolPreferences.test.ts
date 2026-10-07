import { expect, it } from 'vitest'
import { enabledTools, effectiveTools, updateToolPreferences } from './threadToolPreferences'

const profiles = [
  { profileId: 'pp', profileVersion: '1.0', displayName: 'PP', implementationFamilies: ['pandapower'] },
  { profileId: 'ps', profileVersion: '1.0', displayName: 'PS', implementationFamilies: ['pypsa'] },
]

it('defaults every registered tool on, including newly registered groups', () => {
  expect(enabledTools(profiles, [])).toHaveLength(2)
  expect(enabledTools([...profiles, { ...profiles[0], profileId: 'new' }], ['pp'])).toHaveLength(2)
})

it('keeps global choices independent of models and versions', () => {
  const disabled = updateToolPreferences(profiles, [], [profiles[1]])
  expect(disabled).toEqual(['pp'])
  expect(effectiveTools(profiles, disabled, 'pandapower')).toEqual([])
  expect(effectiveTools(profiles, disabled, 'pypsa')).toEqual([profiles[1]])
  expect(enabledTools([{ ...profiles[0], profileVersion: '2.0' }, profiles[1]], disabled)).toEqual([profiles[1]])
})

it('preserves preferences for groups temporarily absent from the catalog', () => {
  expect(updateToolPreferences([profiles[1]], ['pp', 'missing'], [])).toEqual(['pp', 'missing', 'ps'])
})
