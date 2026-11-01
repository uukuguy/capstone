import {expect,it} from 'vitest'
import {instructionProductScopesFromEvents} from './instructionProducts'
import type {EventEnvelope} from './threadProtocol'
const event=(eventSeq:number,attemptId:string,kind='send_auto'):EventEnvelope=>({eventId:`e${eventSeq}`,eventSeq,eventType:'command_accepted',eventVersion:1,threadId:'thread',runId:'run',visibility:'public',occurredAt:'2026-11-01T00:00:00Z',attemptId,payload:{kind,payload:{text:`问题 ${attemptId}`}}})
it('numbers persisted instructions independently of event arrival order and control commands',()=>{
  const rows=[event(30,'c'),event(10,'a'),event(20,'b','send_message'),event(25,'control','cancel')]
  const scopes=instructionProductScopesFromEvents(rows)
  expect([...scopes.values()].map(scope=>[scope.attemptId,scope.number])).toEqual([['a',1],['b',2],['c',3]])
  expect(instructionProductScopesFromEvents([...rows,rows[0]]).get('c')).toEqual(scopes.get('c'))
})
