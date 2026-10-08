import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { PageHeader } from './AppHeader'

it('shows the build revision beside the product name', () => {
  render(<PageHeader />)
  const version = screen.getByLabelText('App 版本')
  expect(version.textContent).toMatch(/^v0\.1\.0 · (?:[a-f0-9]{7}|开发版)$/)
  expect(version.getAttribute('title')).toContain('源代码版本')
})
