/** Opening purpose of one model call. A leading // comment wins; otherwise a short first line. */
export function responseOpeningIntent(text?: string): string | undefined {
  const first = text?.trimStart().split(/\r?\n/, 1)[0].trim()
  if (!first) return undefined
  const purpose = first.startsWith('//') ? first.slice(2).trim() : first
  if (!first.startsWith('//') && (purpose.length > 80 || /^[{[`]|```/.test(purpose))) return undefined
  if (!purpose || /(?:api[_ -]?key|access[_ -]?token|authorization|password|secret)["']?\s*[:=]/i.test(purpose)) return undefined
  return purpose.slice(0, 160)
}

/** Read an explicit script comment; never turn executable source into a title. */
export function scriptOpeningIntent(command:string):string|undefined {
  const action=command.replace(/^\s*cd\s+(?:'[^']*'|"[^"]*"|[^\s;&|]+)[ \t]*(?:&&|;|\r?\n)\s*/, '')
  const lines=action.split(/\r?\n|\\n/),first=lines[0]?.trim()??''
  const comment=first.startsWith('#')?first:/<<-?\s*['"]?\w+['"]?\s*$/.test(first)?lines.slice(1).find(line=>line.trim())?.trim():undefined
  if(!comment?.startsWith('#')||comment.startsWith('#!'))return
  const intent=comment.replace(/^#+\s*/,'').trim().slice(0,120)
  return intent&&!/(?:api[_ -]?key|token|authorization|password|secret)["']?\s*[:=]/i.test(intent)?intent:undefined
}
