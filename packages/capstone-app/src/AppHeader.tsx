import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { isAppBuildIdentity } from './appBuild'
import type { AppBuildIdentity } from './appBuild'

function Mark() {
  return <span className="mark" aria-hidden="true"><i /><i /><i /><i /></span>
}

export function AppVersion({ build }: { build: AppBuildIdentity }) {
  const environment = build.environment ?? '环境未配置'
  return <span className="app-version" aria-label="App 版本"
    title={`环境：${environment}；源代码版本：${build.revision || '本地开发'}${build.dirty ? '（含未提交修改）' : ''}`}>
    {environment} · v{build.version} · {build.revision.slice(0, 7) || '开发版'}{build.dirty ? ' *' : ''}
  </span>
}

export function PageHeader({ className = '', showThreadEntry = true, actions }: { className?: string; showThreadEntry?: boolean; actions?: ReactNode }) {
  const [build, setBuild] = useState(__CAPSTONE_BUILD__)
  useEffect(() => {
    if (!import.meta.env.DEV || import.meta.env.MODE === 'test') return
    let active = true
    const refresh = () => {
      if (document.visibilityState === 'hidden') return
      void fetch('/__capstone-build').then(response => response.ok ? response.json() : null).then(value => {
        if (active && isAppBuildIdentity(value)) setBuild(value)
      }).catch(() => {})
    }
    refresh()
    const timer = window.setInterval(refresh, 30_000)
    window.addEventListener('focus', refresh)
    return () => { active = false; window.clearInterval(timer); window.removeEventListener('focus', refresh) }
  }, [])
  const projectLink = <a className="project-link" href="https://github.com/uukuguy/capstone"
      target="_blank" rel="noopener noreferrer" aria-label="在 GitHub 查看 CAPSTONE 项目源代码" title="在 GitHub 查看 CAPSTONE 项目源代码">
      <svg className="project-link-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
        <path d="M6.766 11.328c-2.063-.25-3.516-1.734-3.516-3.656 0-.781.281-1.625.75-2.188-.203-.515-.172-1.609.063-2.062.625-.078 1.468.25 1.968.703.594-.187 1.219-.281 1.985-.281.765 0 1.39.094 1.953.265.484-.437 1.344-.765 1.969-.687.218.422.25 1.515.046 2.047.5.593.766 1.39.766 2.203 0 1.922-1.453 3.375-3.547 3.64.531.344.89 1.094.89 1.954v1.625c0 .468.391.734.86.547C13.781 14.359 16 11.53 16 8.03 16 3.61 12.406 0 7.984 0 3.563 0 0 3.61 0 8.031a7.88 7.88 0 0 0 5.172 7.422c.422.156.828-.125.828-.547v-1.25c-.219.094-.5.156-.75.156-1.031 0-1.64-.562-2.078-1.609-.172-.422-.36-.672-.719-.719-.187-.015-.25-.093-.25-.187 0-.188.313-.328.625-.328.453 0 .844.281 1.25.86.313.452.64.655 1.031.655s.641-.14 1-.5c.266-.265.47-.5.657-.656" />
      </svg>
    </a>
  return <header className={`topbar ${className}`.trim()}>
    <div className="brand"><Mark /><span className="brand-name">CAPSTONE</span>
      <AppVersion build={build} /><span className="brand-divider" />
      <span className="brand-subtitle">电网分析工作台</span></div>
    {actions ? <div className="topbar-right">{actions}{projectLink}</div> : <>
      {showThreadEntry && <a className="thread-entry-link" href="/?thread=new">打开 Thread</a>}
      {projectLink}
    </>}
  </header>
}
