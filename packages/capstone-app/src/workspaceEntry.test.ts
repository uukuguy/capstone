import {afterEach,expect,it} from 'vitest'
import {rememberWorkspaceThread,readLastWorkspaceThread,forgetWorkspaceThread} from './workspaceEntry'
afterEach(()=>forgetWorkspaceThread())
it('remembers a public identity across entry reload and removes only the missing selected identity',()=>{
  rememberWorkspaceThread('thr_saved')
  expect(readLastWorkspaceThread()).toBe('thr_saved')
  forgetWorkspaceThread('thr_other');expect(readLastWorkspaceThread()).toBe('thr_saved')
  rememberWorkspaceThread('new');expect(readLastWorkspaceThread()).toBe('thr_saved')
  forgetWorkspaceThread('thr_saved');expect(readLastWorkspaceThread()).toBeUndefined()
})
