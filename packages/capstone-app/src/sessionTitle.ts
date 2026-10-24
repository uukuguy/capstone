export type SessionTitle = {
  text: string
  source: 'default' | 'automatic' | 'user'
  revision: number
  source_ref: string | null
}

export function parseSessionTitle(value: unknown): SessionTitle {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('会话标题无效')
  const item = value as Record<string, unknown>
  if (Object.keys(item).sort().join(',') !== 'revision,source,source_ref,text'
    || typeof item.text !== 'string' || !item.text.trim() || item.text !== item.text.trim()
    || Array.from(item.text).length > 160 || /[\u0000-\u001f]/.test(item.text)
    || !['default', 'automatic', 'user'].includes(String(item.source))
    || !Number.isSafeInteger(item.revision) || (item.revision as number) < 0
    || !(item.source_ref === null || typeof item.source_ref === 'string' && Boolean(item.source_ref.trim()) && item.source_ref.length <= 512)
    || (item.source === 'automatic') !== (item.source_ref !== null)) throw new Error('会话标题无效')
  return {...item} as SessionTitle
}
