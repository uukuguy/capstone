/** Explicit response metadata only. Never derive purpose from model reasoning. */
export function responseOpeningIntent(text?: string): string | undefined {
  const first = text?.split(/\r?\n/, 1)[0].trim()
  if (!first?.startsWith('//')) return undefined
  return first.slice(2).trim().slice(0, 160) || undefined
}
