import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import App from './App'

afterEach(() => { cleanup(); window.history.replaceState({}, '', '/') })

describe('Thread fixture entry point', () => {
  it('opens the fixture workspace without bootstrapping the legacy Case API', async () => {
    window.history.replaceState({}, '', '/?thread-fixture=idle-ieee39')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Thread / IEEE-39' })).toBeTruthy()
    expect(screen.queryByText('案例库')).toBeNull()
  })
})
