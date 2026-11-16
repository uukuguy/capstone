import {expect,it} from 'vitest'
import {PinState,parsePinState} from './durableSessionPins'

it('retains confirmed pins after failed refresh and ignores stale responses',async()=>{
  let response:unknown={schema:'capstone-session-pins/1',workspace:'enterprise',revision:4,pins:['a']}
  const state=new PinState('enterprise',{read:async()=>{if(response instanceof Error)throw response;return response},write:async()=>response})
  await state.refresh()
  response=new Error('offline');await state.refresh()
  expect(state.snapshot.pins).toEqual(['a'])
  expect(state.snapshot.error).toBeTruthy()
  response={schema:'capstone-session-pins/1',workspace:'enterprise',revision:3,pins:[]};await state.refresh()
  expect(state.snapshot.pins).toEqual(['a'])
})
it('rejects another workspace and malformed pin projections',()=>{
  expect(()=>parsePinState({schema:'capstone-session-pins/1',workspace:'other',revision:1,pins:[]},'enterprise')).toThrow()
  expect(()=>parsePinState({schema:'capstone-session-pins/1',workspace:'enterprise',revision:-1,pins:[]},'enterprise')).toThrow()
})

it('serializes rapid toggles and imports without replacing the saved list',async()=>{
  let saved={schema:'capstone-session-pins/1' as const,workspace:'enterprise',revision:1,pins:['old']}
  const operations:unknown[]=[]
  const state=new PinState('enterprise',{read:async()=>saved,write:async operation=>{
    operations.push(operation)
    saved={...saved,revision:saved.revision+1,pins:'import' in operation?[...new Set([...saved.pins,...operation.import])]:operation.pinned?[...saved.pins,operation.thread_id]:saved.pins.filter(id=>id!==operation.thread_id)}
    return saved
  }})
  await state.import(['legacy'])
  expect(state.snapshot.pins).toEqual(['old','legacy'])
  await Promise.all([state.toggle('new'),state.toggle('new')])
  expect(state.snapshot.pins).toEqual(['old','legacy'])
  expect(operations.slice(-2)).toEqual([{thread_id:'new',pinned:true},{thread_id:'new',pinned:false}])
})
