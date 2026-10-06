import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import App from './App'

beforeEach(() => vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
  schema: 'capstone-thread-access/1', mode: 'operator',
})))))
afterEach(() => { cleanup(); window.history.replaceState({}, '', '/'); vi.unstubAllGlobals() })

describe('Thread fixture entry point', () => {
  it('opens the live Thread entry by default at the root path', async () => {
    window.history.replaceState({}, '', '/')
    sessionStorage.removeItem('capstone.thread.operatorToken')
    render(<App />)
    expect(await screen.findByRole('heading', { name: '连接 Thread' })).toBeTruthy()
    expect(screen.queryByText('案例库')).toBeNull()
  })
  it('opens the fixture workspace without bootstrapping the legacy Case API', async () => {
    window.history.replaceState({}, '', '/?thread-fixture=idle-ieee39')
    render(<App />)

    expect(await screen.findByRole('region', { name: '电网模型区' })).toBeTruthy()
    expect(screen.queryByText('案例库')).toBeNull()
  })

  it('opens the live Thread entry without bootstrapping the legacy Case API', async () => {
    window.history.replaceState({}, '', '/?thread=thr_demo_39')
    sessionStorage.removeItem('capstone.thread.operatorToken')
    render(<App />)

    expect(await screen.findByRole('heading', { name: '连接 Thread' })).toBeTruthy()
    expect(screen.getByLabelText('Operator token')).toBeTruthy()
    expect(screen.queryByText('案例库')).toBeNull()
  })
})
