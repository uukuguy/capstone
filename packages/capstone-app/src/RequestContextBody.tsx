const jsonToken = /"(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null|[{}\[\]:,]/g

export default function RequestContextBody({text}: {text: string}) {
  if (!/^[\s]*[{\[]/.test(text)) return <pre>{text}</pre>
  try {
    JSON.parse(text)
  } catch {
    return <pre>{text}</pre>
  }

  // Keep the original tokens so formatting preserves numbers, escapes, and repeated keys.
  const tokens = text.match(jsonToken) ?? []
  let depth = 0
  const newline = () => '\n' + '  '.repeat(depth)
  return <pre className="context-json" aria-label="JSON 正文"><code>{tokens.map((token, index) => {
    const previous = tokens[index - 1]
    const next = tokens[index + 1]
    if (token === '{' || token === '[') {
      depth++
      return token + (next === '}' || next === ']' ? '' : newline())
    }
    if (token === '}' || token === ']') {
      depth--
      return (previous === '{' || previous === '[' ? '' : newline()) + token
    }
    if (token === ',') return token + newline()
    if (token === ':') return ': '
    const kind = token.startsWith('"') ? (next === ':' ? 'key' : 'string')
      : /^[\d-]/.test(token) ? 'number' : 'literal'
    return <span key={index} className={`context-json-${kind}`}>{token}</span>
  })}</code></pre>
}
