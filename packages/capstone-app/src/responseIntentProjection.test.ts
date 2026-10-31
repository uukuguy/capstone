import {expect,it} from 'vitest'
import {ResponseIntentProjection} from './responseIntentProjection'
import type {EventEnvelope} from './threadProtocol'
const row=(n:number,type:string,payload:Record<string,unknown>,visibility='public'):EventEnvelope=>({eventId:`e${n}`,eventSeq:n,eventType:type,eventVersion:1,threadId:'t',attemptId:'a',occurredAt:'2026-10-31T00:00:00Z',visibility,payload} as EventEnvelope)
it('keeps explicit purpose after diagnostic eviction without publishing response bodies or reasoning',()=>{
 const p=new ResponseIntentProjection(),start=row(1,'runtime_action',{phase:'started'})
 const a=row(2,'assistant_process_delta',{text:'// 检查'},'diagnostic')
 p.observe([start,a]);expect(p.intent('e1')).toBe('检查')
 const b=row(4,'assistant_process_delta',{text:'字段\nPRIVATE BODY'},'diagnostic')
 p.observe([start,a,row(3,'assistant_thinking_delta',{text:'PRIVATE REASONING'}),b])
 p.observe([start,row(5,'runtime_action',{phase:'response_completed'})])
 expect(p.intent('e1')).toBe('检查字段')
 p.observe([]);expect(p.intent('e1')).toBeUndefined()
})
it('does not guess from prose or publish protected comment values',()=>{
 for(const text of ['Actual answer','// password=private']){
  const p=new ResponseIntentProjection();p.observe([row(1,'runtime_action',{phase:'started'}),row(2,'assistant_process_delta',{text},'diagnostic')])
  expect(p.intent('e1')).toBeUndefined()
 }
})
