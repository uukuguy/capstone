import {exceedsCapacity} from './applicationCapacity'
export type SessionTitle = {
  text: string
  source: 'default' | 'automatic' | 'user'
  revision: number
  source_ref: string | null
}

export function displaySessionTitle(title: Pick<SessionTitle, 'text' | 'source'>): string {
  if (title.source !== 'default') return title.text
  const match = /^(.*) · (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)$/.exec(title.text)
  if (!match) return title.text
  const date = new Date(match[2])
  if (!Number.isFinite(date.getTime())) return title.text
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${match[1]} · ${pad(date.getMonth()+1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

export function parseSessionTitle(value: unknown): SessionTitle {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('会话标题无效')
  const item = value as Record<string, unknown>
  if (Object.keys(item).sort().join(',') !== 'revision,source,source_ref,text'
    || typeof item.text !== 'string' || !item.text.trim() || item.text !== item.text.trim()
    || exceedsCapacity(Array.from(item.text).length,'ui_session_title_chars') || /[\u0000-\u001f]/.test(item.text)
    || !['default', 'automatic', 'user'].includes(String(item.source))
    || !Number.isSafeInteger(item.revision) || (item.revision as number) < 0
    || !(item.source_ref === null || typeof item.source_ref === 'string' && Boolean(item.source_ref.trim()) && item.source_ref.length <= 512)
    || (item.source === 'automatic') !== (item.source_ref !== null)) throw new Error('会话标题无效')
  return {...item} as SessionTitle
}
