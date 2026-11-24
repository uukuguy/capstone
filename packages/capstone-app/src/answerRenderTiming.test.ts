import {expect,it,vi} from 'vitest'
import {consumeAnswerArrival,recordAnswerArrival} from './answerRenderTiming'

it('measures one live arrival per attempt and ignores restored answers',()=>{
 const now=vi.spyOn(performance,'now').mockReturnValue(50)
 try{
  recordAnswerArrival('attempt-a')
  now.mockReturnValue(100)
  recordAnswerArrival('attempt-a')
  expect(consumeAnswerArrival('attempt-b')).toBeUndefined()
  expect(consumeAnswerArrival('attempt-a')).toBe(50)
  expect(consumeAnswerArrival('attempt-a')).toBeUndefined()
 }finally{now.mockRestore()}
})
