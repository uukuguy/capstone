import {afterEach,expect,it,vi} from 'vitest'
import {observeServerClock,resetServerClock,serverNow} from './serverClock'
afterEach(()=>{resetServerClock();vi.restoreAllMocks()})
it('uses the API time domain even when the browser is 327 seconds ahead',()=>{
 const epoch=Date.parse('2026-11-01T11:00:00Z')
 vi.spyOn(Date,'now').mockReturnValue(epoch+327000)
 vi.spyOn(performance,'now').mockReturnValue(200)
 observeServerClock('Sun, 01 Nov 2026 11:00:00 GMT',0,100)
 expect(serverNow()).toBe(epoch+650)
})
it('ignores missing dates and slow samples instead of overwriting a good clock',()=>{
 vi.spyOn(performance,'now').mockReturnValue(100)
 observeServerClock('Sun, 01 Nov 2026 11:00:00 GMT',0,100)
 const before=serverNow();observeServerClock(null,0,100);observeServerClock('Sun, 01 Nov 2026 12:00:00 GMT',0,5000)
 expect(serverNow()).toBe(before)
})
