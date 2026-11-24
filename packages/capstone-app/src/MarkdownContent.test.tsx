import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import MarkdownContent from './MarkdownContent'

afterEach(cleanup)

it('shows all rows when a saved answer has literal n table separators', () => {
  const text = '| 母线编号 | 标幺电压 |\n| --- | --- |\n| 2 | 1.01 |n| 3 | 1.0177 |n| 4 | 1.0195 |'
  render(<MarkdownContent>{text}</MarkdownContent>)
  expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(4)
  expect(screen.getByRole('cell', {name:'1.0195'})).toBeTruthy()
})

it('keeps identical text literal inside a code fence and outside a table', () => {
  const row = '| 2 | 1.01 |n| 3 | 1.0177 |'
  const text = ['```markdown', '| Bus | Value |', '| --- | --- |', row, '```', '', row].join('\n')
  const {container} = render(<MarkdownContent>{text}</MarkdownContent>)
  expect(screen.queryByRole('table')).toBeNull()
  expect(screen.getByText(row)).toBeTruthy()
  expect(container.querySelector('pre code')?.textContent).toContain(row)
})
