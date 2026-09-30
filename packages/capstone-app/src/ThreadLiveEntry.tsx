import { FormEvent, useEffect, useMemo, useState } from 'react'
import ThreadFixtureApp from './ThreadFixtureApp'
import { CapstoneThreadClient } from './threadClient'
import { HttpThreadTransport } from './threadHttpTransport'

const TOKEN_KEY = 'capstone.thread.operatorToken'

function readToken(): string {
  try { return sessionStorage.getItem(TOKEN_KEY) || '' } catch { return '' }
}

function TokenPrompt({ onSubmit }: { onSubmit: (token: string) => void }) {
  const [value, setValue] = useState('')
  function submit(event: FormEvent) {
    event.preventDefault()
    const token = value.trim()
    if (!token) return
    try { sessionStorage.setItem(TOKEN_KEY, token) } catch { /* memory-only fallback */ }
    onSubmit(token)
  }
  return <main className="thread-token-shell">
    <form className="thread-token-card" onSubmit={submit}>
      <span className="eyebrow">CAPSTONE / PRIVATE THREAD</span>
      <h1>连接 Thread</h1>
      <p>输入本地或受信任服务的 operator token。Token 只保存在当前浏览器会话中。</p>
      <label>Operator token<input aria-label="Operator token" type="password" value={value} onChange={(event) => setValue(event.target.value)} autoComplete="off" /></label>
      <button type="submit" disabled={!value.trim()}>连接</button>
    </form>
  </main>
}

export default function ThreadLiveEntry({ threadId }: { threadId: string }) {
  const [token, setToken] = useState(readToken)
  const [createdThreadId, setCreatedThreadId] = useState(threadId === 'new' ? '' : threadId)
  const [creating, setCreating] = useState(threadId === 'new')
  const [error, setError] = useState<string | null>(null)
  const apiOrigin = import.meta.env.VITE_API_ORIGIN || ''
  const transport = useMemo(
    () => token ? new HttpThreadTransport(apiOrigin, token) : null,
    [apiOrigin, token],
  )
  const client = useMemo(() => transport ? new CapstoneThreadClient(transport) : null, [transport])

  useEffect(() => {
    if (!client || threadId !== 'new' || createdThreadId) return
    let active = true
    setCreating(true); setError(null)
    void client.create('ieee39').then((snapshot) => {
      if (active) setCreatedThreadId(snapshot.threadId)
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : 'Thread 创建失败')
    }).finally(() => { if (active) setCreating(false) })
    return () => { active = false }
  }, [client, createdThreadId, threadId])

  if (!token) return <TokenPrompt onSubmit={setToken} />
  if (error) return <main className="thread-token-shell"><div className="thread-token-card" role="alert"><h1>Thread 不可用</h1><p>{error}</p><button type="button" onClick={() => { setError(null); setToken('') }}>更换 token</button></div></main>
  if (creating || !client || !createdThreadId) return <main className="thread-loading" aria-live="polite"><span className="spinner" />正在创建 Thread…</main>
  return <ThreadFixtureApp client={client} threadId={createdThreadId} />
}
