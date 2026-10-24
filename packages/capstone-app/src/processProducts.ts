import {exceedsCapacity} from './applicationCapacity'
import { parseContext, type ModelContextSnapshot } from './threadProtocol'

export type ProcessProduct = {
  productId: string; threadId: string; attemptId: string; workId: string | null
  instruction: string; status: 'completed' | 'failed' | 'cancelled' | 'interrupted'
  eventSeq: number; occurredAt: string; failureCode: string | null
  modelContext: ModelContextSnapshot | null
}
export type ProcessProductPage = {products: ProcessProduct[]; hasMore: boolean; nextBefore: number}

export function parseProcessProducts(value: unknown, threadId: string, before?: number): ProcessProductPage {
  const page = value as Record<string, unknown> | null
  if (!page || page.schema !== 'capstone-process-products/1' || page.thread_id !== threadId
    || !Array.isArray(page.products) || exceedsCapacity(page.products.length,'product_page_items') || typeof page.has_more !== 'boolean'
    || !Number.isSafeInteger(page.next_before_event_seq) || (page.next_before_event_seq as number) < 1
    || before !== undefined && (page.next_before_event_seq as number) > before
    || page.has_more && before !== undefined && page.next_before_event_seq === before) throw new Error('过程制品目录无效')
  const seen = new Set<string>()
  const products = page.products.map((item: Record<string, unknown>) => {
    if (!item || item.scope !== 'instruction' || item.thread_id !== threadId || item.historical_only !== true
      || typeof item.attempt_id !== 'string' || !/^[a-z][a-z0-9_-]{0,63}$/.test(item.attempt_id)
      || item.product_id !== `process_${item.attempt_id}` || seen.has(item.product_id as string)
      || typeof item.instruction !== 'string' || exceedsCapacity(Array.from(item.instruction).length,'input_text_chars')
      || !['completed','failed','cancelled','interrupted'].includes(String(item.status))
      || !Number.isSafeInteger(item.event_seq) || (item.event_seq as number) < 1
      || before !== undefined && (item.event_seq as number) >= before
      || typeof item.occurred_at !== 'string' || !Number.isFinite(Date.parse(item.occurred_at))
      || !(item.work_id === null || typeof item.work_id === 'string')
      || !(item.failure_code === null || typeof item.failure_code === 'string' && /^[a-z][a-z0-9_]{0,127}$/.test(item.failure_code))) throw new Error('过程制品身份无效')
    seen.add(item.product_id as string)
    return {productId:item.product_id as string,threadId,attemptId:item.attempt_id,workId:item.work_id as string | null,
      instruction:item.instruction,status:item.status as ProcessProduct['status'],eventSeq:item.event_seq as number,
      occurredAt:item.occurred_at,failureCode:item.failure_code as string | null,
      modelContext:item.model_context === null ? null : parseContext(item.model_context)}
  })
  return {products,hasMore:page.has_more,nextBefore:page.next_before_event_seq as number}
}
