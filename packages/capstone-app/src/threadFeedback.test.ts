import { describe, expect, it } from 'vitest'
import { commandRejectionCopy, toolFailureReason } from './threadFeedback'

describe('recorded tool failure reasons', () => {
  it('summarizes nested JSON errors instead of showing the JSON envelope',()=>{
    expect(toolFailureReason({message:JSON.stringify({error:{code:'query_failed',message:'字段不存在'},trace:'internal'})})).toBe('字段不存在')
  })
  it('explains rejected revision conflicts and retained input',()=>{
    expect(commandRejectionCopy('revision_conflict')).toContain('未执行')
    expect(commandRejectionCopy('revision_conflict')).toContain('输入内容已保留')
  })
  it.each(['{"detail":','{"detail":{"unexpected":true}}'])('keeps malformed or unrecognized JSON out of the summary: %s',message=>{
    expect(toolFailureReason({message})).toBe('工具返回错误；请展开原始诊断查看详情。')
  })
  it('unwraps MCP content and gateway gaps',()=>{
    const message=JSON.stringify({content:[{type:'text',text:JSON.stringify({status:'error',gaps:[{reason:'query_timeout',message:'Database query exceeded the time budget'}]})}]})
    expect(toolFailureReason({message})).toBe('Database query exceeded the time budget')
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
