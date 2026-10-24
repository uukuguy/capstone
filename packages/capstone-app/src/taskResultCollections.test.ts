import { describe, expect, it } from 'vitest'
import { taskResultCollections } from './taskResultCollections'
import type { ResultProjection } from './threadProtocol'

const result: ResultProjection = {resultId:'r',threadId:'t',runId:'run',turnId:'turn',attemptId:'a',modelContextId:'ctx',modelId:'grid',modelRevision:'revision',evidenceRefs:[],source:{capabilityId:'analysis',domainPackId:'pack',implementationFamily:'test'},status:'completed',summary:[],tables:[],elementRefs:[]}
const presentation = {collectionId:'analysis',collectionTitle:'分析结果',groupId:'state',groupTitle:'运行状态',purpose:'task_output' as const}
describe('instruction process collections', () => {
  it('keeps current and legacy result groups at instruction scope', () => {
    for (const purpose of ['process_output', 'task_output'] as const) {
      const collections = taskResultCollections([{...result,presentation:{...presentation,purpose}}], 'a')
      expect(collections).toHaveLength(1)
      expect(collections[0].scope).toBe('instruction')
    }
  })
  it('does not infer membership for legacy or inspection results', () => {
    expect(taskResultCollections([result,{...result,presentation:{...presentation,purpose:'inspection'}}], 'a')).toEqual([])
  })
  it('keeps other instructions and packs separate', () => {
    const first = {...result,presentation}
    const second = {...first,resultId:'r2'}
    const otherPack = {...first,resultId:'r3',source:{...result.source,domainPackId:'other'}}
    const collections = taskResultCollections([first,second,{...first,attemptId:'old'},otherPack], 'a')
    expect(collections).toHaveLength(2)
    expect(collections[0].results).toEqual([first,second])
    expect(collections[1].results).toEqual([otherPack])
  })
})
