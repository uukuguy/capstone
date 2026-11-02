import {afterEach,expect,it} from 'vitest'
import {readSessionPins} from './sessionNavigationState'
afterEach(()=>localStorage.clear())
const origin='capstone.thread.http%3A%2F%2Flocalhost%3A5173.'
it('recovers pins from earlier tabs and keeps workspaces separate',()=>{
  localStorage.setItem(`capstone.session-pins:${origin}old-tab`,JSON.stringify(['a']))
  localStorage.setItem(`capstone.session-pins:${origin}other-tab`,JSON.stringify(['b']))
  localStorage.setItem(`capstone.session-pins:${origin}old-tab.workspace.grid`,JSON.stringify(['grid']))
  expect(readSessionPins(`${origin}new-tab`)).toEqual(['a','b'])
  expect(readSessionPins(`${origin}new-tab.workspace.grid`)).toEqual(['grid'])
})
it('preserves unknown pin protection when a legacy record is corrupt',()=>{
  for(const value of ['not-json','{}','["a",7]']){
    localStorage.clear()
    localStorage.setItem(`capstone.session-pins:${origin}old-tab`,value)
    expect(readSessionPins(`${origin}new-tab`)).toBeUndefined()
    expect(localStorage.length).toBe(1)
  }
})
