import {expect,it} from 'vitest'
import {parseSessionSkills} from './sessionSkills'
import {buildInputSubmission,emptyInputDraft,readInputDraft} from './threadInput'

it('restores versioned preferences and rejects duplicate or professional choices',()=>{
  const value={revision:2,skills:[{id:'method',version:'v1',role:'delegated_pi'}]}
  expect(parseSessionSkills(value)).toEqual(value)
  expect(()=>parseSessionSkills({...value,skills:[...value.skills,...value.skills]})).toThrow()
  expect(()=>parseSessionSkills({...value,skills:[{...value.skills[0],role:'harness_engine'}]})).toThrow()
  expect(parseSessionSkills(undefined)).toEqual({revision:0,skills:[]})
})

it('rejects malformed saved per-instruction exclusions',()=>{
  const malformed={...emptyInputDraft('capstone'),excluded_session_skills:'method'}
  sessionStorage.setItem('bad-exclusion.input',JSON.stringify(malformed))
  expect(readInputDraft('bad-exclusion')).toBeUndefined()
  expect(()=>buildInputSubmission('continue',malformed as never)).toThrow()
})
