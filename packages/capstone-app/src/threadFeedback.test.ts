import { describe, expect, it } from 'vitest'
import { commandRejectionCopy, toolFailureReason } from './threadFeedback'

describe('recorded tool failure reasons', () => {
  it('shows the indexed failed subquery and preserves its parent request', () => {
    const summary=toolFailureReason({summary:JSON.stringify({status:'error',provenance:{request_id:'parent'},gaps:[{message:'See subquery',scope:{query_index:1}}],data:[{result:{status:'error',error:{message:'wrong child'}}},{result:{status:'error',gaps:[{reason:'ambiguous_data_source',message:'Select source_id explicitly'}]}}]})})!
    expect(summary).toContain('Select source_id explicitly')
    expect(summary).toContain('parent')
    expect(summary).not.toContain('wrong child')
  })
  it('labels preserved backend diagnostic fields for the reader',()=>{
    const summary=toolFailureReason({summary:'排序字段无效；path=/order_by/0；executed=false；rejected_value=-DATE；legal_values_source=columns[].name；suggestion=使用原字段名'})!
    for(const expected of ['未执行','拒绝值=-DATE','合法值来源=columns[].name','纠正建议=使用原字段名'])expect(summary).toContain(expected)
  })
  it('shows rejected values, legal-value sources and explicit non-execution from a gap scope',()=>{
    const message=JSON.stringify({structuredContent:{status:'error',gaps:[{reason:'invalid_arguments',message:'排序字段无效',scope:{path:'/order_by/0',rejected_value:'-DATE',legal_values_source:'columns[].name',suggestion:'使用原字段名，不加倒序前缀',executed:false}}],provenance:{request_id:'rejected-sort-request'}}})
    const summary=toolFailureReason({summary:message})!
    for(const expected of ['排序字段无效','/order_by/0','-DATE','columns[].name','未执行','rejected-sort-request','使用原字段名'])expect(summary).toContain(expected)
  })
  it('does not imply an error was unexecuted when the gateway did not say so',()=>{
    const summary=toolFailureReason({summary:JSON.stringify({status:'error',gaps:[{reason:'invalid_arguments',message:'参数无效'}]})})!
    expect(summary).not.toContain('未执行')
  })
  it('does not expose a rejected credential value in a diagnostic',()=>{
    const summary=toolFailureReason({summary:JSON.stringify({status:'error',gaps:[{reason:'invalid_arguments',message:'参数无效',path:'/access_token',rejected_value:'private-canary',executed:false}]})})!
    expect(summary).not.toContain('private-canary')
    expect(summary).toContain('/access_token')
    expect(summary).toContain('未执行')
  })
  it('summarizes nested JSON errors instead of showing the JSON envelope',()=>{
    expect(toolFailureReason({message:JSON.stringify({error:{code:'query_failed',message:'字段不存在'},trace:'internal'})})).toBe('字段不存在')
  })
  it('explains rejected revision conflicts and retained input',()=>{
    expect(commandRejectionCopy('revision_conflict')).toContain('未执行')
    expect(commandRejectionCopy('revision_conflict')).toContain('输入内容已保留')
  })
  it('reads a grid tool error that is followed by host guidance', () => {
    const summary = toolFailureReason({ summary: '{"code": "powerflow_non_converged", "phase": "execute", "message": "Pandapower AC power flow did not converge"} Inspect the evidence and correct or justify this selection.' })!
    expect(summary).toContain('Pandapower AC power flow did not converge')
    expect(summary).not.toContain('格式不可识别')
  })
  it('reads a cut-off grid error that still contains its message', () => {
    const summary = toolFailureReason({ summary: '{"code": "analysis_non_converged", "message": "Analysis operation \'powerflow.ac\' did not converge", "retryab' })!
    expect(summary).toContain('did not converge')
  })
  it.each(['{"detail":','{"detail":{"unexpected":true}}'])('keeps malformed or unrecognized JSON out of the summary: %s',message=>{
    expect(toolFailureReason({message})).toBe('诊断摘要不完整或格式不可识别；请查看保存的原始响应。')
  })
  it('unwraps MCP content and gateway gaps',()=>{
    const message=JSON.stringify({content:[{type:'text',text:JSON.stringify({status:'error',gaps:[{reason:'query_timeout',message:'Database query exceeded the time budget'}]})}]})
    expect(toolFailureReason({message})).toBe('Database query exceeded the time budget')
  })
  it('reads structured MCP errors and preserves their request identifier',()=>{
    const message=JSON.stringify({structuredContent:{status:'error',gaps:[{reason:'invalid_arguments',message:'Unknown source field',scope:{path:'/order_by/0'}}],provenance:{request_id:'request-123'}}})
    expect(toolFailureReason({summary:message})).toContain('Unknown source field')
    expect(toolFailureReason({summary:message})).toContain('/order_by/0')
    expect(toolFailureReason({summary:message})).toContain('request-123')
  })
  it('renders a legacy English diagnostic with a Chinese category reason', () => {
    expect(toolFailureReason({ code: 'analysis_prerequisite_missing', message: 'Missing model inputs' }))
      .toBe('缺少必要参数，未产生结果；此记录未保存缺失项。')
  })
  it('prefers the actual structured reason over a generic category', () => {
    expect(toolFailureReason({ code: 'result_field_unavailable', message: 'Query rejected',
      summary: '字段不可用：bus；可用字段：index、vm_pu' }))
      .toBe('字段不可用：bus；可用字段：index、vm_pu')
  })
  it('retains an existing reader-language reason for an unknown category', () => {
    expect(toolFailureReason({ code: 'custom_failure', message: '缺少场景边界。' })).toBe('缺少场景边界。')
  })
})
