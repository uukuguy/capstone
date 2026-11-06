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
it('keeps a short opening line and still hides a protected comment',()=>{
 const shown=new ResponseIntentProjection()
 shown.observe([row(1,'runtime_action',{phase:'started'}),row(2,'assistant_process_delta',{text:'核对字段与来源\n正文'},'diagnostic')])
 expect(shown.intent('e1')).toBe('核对字段与来源')
 const hidden=new ResponseIntentProjection()
 hidden.observe([row(1,'runtime_action',{phase:'started'}),row(2,'assistant_process_delta',{text:'// password=private'},'diagnostic')])
 expect(hidden.intent('e1')).toBeUndefined()
 const long=new ResponseIntentProjection()
 long.observe([row(1,'runtime_action',{phase:'started'}),row(2,'assistant_process_delta',{text:'甲'.repeat(81)},'diagnostic')])
 expect(long.intent('e1')).toBeUndefined()
})
it('retains the opening comment after leading blank streaming chunks and diagnostic eviction',()=>{
 const p=new ResponseIntentProjection(),start=row(1,'runtime_action',{phase:'started'})
 p.observe([start,row(2,'assistant_process_delta',{text:'\n\n'},'diagnostic')])
 const chunks=[start,row(2,'assistant_process_delta',{text:'\n\n'},'diagnostic'),row(3,'assistant_process_delta',{text:'// 汇总'},'diagnostic'),row(4,'assistant_process_delta',{text:'指标\nPRIVATE BODY'},'diagnostic')]
 p.observe(chunks)
 expect(p.intent('e1')).toBe('汇总指标')
 p.observe([start,row(5,'runtime_action',{phase:'response_completed'})])
 expect(p.intent('e1')).toBe('汇总指标')
})
