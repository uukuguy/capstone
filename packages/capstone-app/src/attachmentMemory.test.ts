import {expect,it} from 'vitest'
import {AttachmentMemory} from './attachmentMemory'

it('bounds concurrent reservations and releases each reservation once',()=>{
  const memory=new AttachmentMemory(()=>10)
  const first=memory.reserve(6)
  expect(()=>memory.reserve(5)).toThrow(/收起/)
  const second=memory.reserve(4)
  first();first()
  const third=memory.reserve(6)
  expect(()=>memory.reserve(1)).toThrow()
  second();third()
  expect(()=>memory.reserve(10)).not.toThrow()
})
it('rejects invalid sizes and applies a changed budget to new reads',()=>{
  let budget=10
  const memory=new AttachmentMemory(()=>budget)
  for(const size of [-1,NaN,Infinity,1.5])expect(()=>memory.reserve(size)).toThrow()
  const release=memory.reserve(8)
  budget=4
  expect(()=>memory.reserve(1)).toThrow()
  release()
  expect(()=>memory.reserve(4)).not.toThrow()
})
