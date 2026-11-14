import {expect,it} from 'vitest'
import {parseSessionSkills} from './sessionSkills'
import {buildInputSubmission,emptyInputDraft,readInputDraft,composerSubmission} from './threadInput'

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

it('preserves content identity and accepted composer exclusions',()=>{
 const choice={id:'method',version:'1',role:'direct_pi',loaded_identity:'a'.repeat(64),native_name:'method',catalog_revision:'catalog'}
 expect(parseSessionSkills({revision:1,skills:[choice]}).skills[0]).toEqual(choice)
 const original=buildInputSubmission('continue',{...emptyInputDraft('pi_reference'),excluded_session_skills:['method']})
 expect(composerSubmission({...original,text:'continue',attachment_refs:['resource_private']})).toEqual(original)
})
