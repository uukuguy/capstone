import { describe, expect, it } from 'vitest'
import { toolFailureReason } from './threadFeedback'

describe('recorded tool failure reasons', () => {
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
