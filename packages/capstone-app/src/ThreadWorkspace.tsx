import { useState, type ReactNode } from 'react'
import { PageHeader } from './AppHeader'

/** Shared application frame. Controllers supply public state and capabilities. */
export default function ThreadWorkspace({ preparation, sidebar, heading, children, loading = false,
  ready = true, subtitle, headerActions, conversationOnly = false }: {
  preparation?: ReactNode; sidebar?: ReactNode; heading?: ReactNode; children?: ReactNode
  loading?: boolean; ready?: boolean; subtitle?: string; headerActions?: ReactNode; conversationOnly?: boolean
}) {
  const [navigationOpen, setNavigationOpen] = useState(false)
  return <div className={`thread-app-shell${conversationOnly ? ' thread-conversation-workspace' : ''}${navigationOpen ? ' is-navigation-open' : ''}`}>
    {preparation}
    <PageHeader className="thread-page-header" showThreadEntry={false} subtitle={subtitle} actions={conversationOnly ? <>
      <button className="thread-navigation-toggle" aria-expanded={navigationOpen} aria-controls="thread-session-navigation" onClick={() => setNavigationOpen(value => !value)}>会话导航</button>
      {headerActions}
    </> : headerActions} />
    {loading && !ready ? <main className="thread-loading" aria-live="polite"><span className="spinner" />正在恢复 Thread 投影…</main>
      : ready ? <main className="thread-app-main"><div className="thread-app-columns">
        {sidebar}
        <section className="thread-chat-pane" aria-label="Thread 对话区">
          {heading}
          {children}
        </section>
      </div></main> : null}
  </div>
}
