import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { AppVersion, PageHeader } from './AppHeader'
import type { AppEnvironment } from './appBuild'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs() })

it('shows the build revision beside the product name', () => {
  render(<PageHeader />)
  const version = screen.getByLabelText('App 版本')
  expect(version.textContent).toMatch(/^环境未配置 · v0\.1\.0 · (?:[a-f0-9]{7}|开发版)$/)
  expect(version.getAttribute('title')).toContain('源代码版本')
})

it.each<AppEnvironment | null>(['local-dev', 'local-demo', 'cloud-dev', 'cloud-demo', null])('shows explicit environment %s beside version and revision', environment => {
  render(<AppVersion build={{ version: '0.1.0', revision: 'a'.repeat(40), dirty: true, environment }} />)
  const version = screen.getByLabelText('App 版本')
  expect(version.textContent).toBe(`${environment ?? '环境未配置'} · v0.1.0 · aaaaaaa *`)
  expect(version.title).toContain('含未提交修改')
})

it('refreshes development environment and retains the label on focus', async () => {
  vi.stubEnv('MODE', 'development')
  vi.stubEnv('DEV', true)
  const fetcher = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({ version: '0.1.0', revision: 'b'.repeat(40), dirty: false, environment: 'local-demo' })))
    .mockResolvedValueOnce(new Response(JSON.stringify({ version: '0.1.0', revision: 'c'.repeat(40), dirty: false, environment: 'cloud-prod' })))
  vi.stubGlobal('fetch', fetcher)
  render(<PageHeader />)
  await waitFor(() => expect(screen.getByLabelText('App 版本').textContent).toBe('local-demo · v0.1.0 · bbbbbbb'))
  fireEvent.focus(window)
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
  expect(screen.getByLabelText('App 版本').textContent).toContain('local-demo')
})
