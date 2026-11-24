import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import MarkdownContent from './MarkdownContent'

afterEach(cleanup)

it('shows an admitted query table in returned order with its unit', () => {
  const text = [
    '三行均高于 0.95。',
    '',
    '| index | vm_pu (p.u.) |',
    '| --- | --- |',
    '| 2 | 1.01 |',
    '| 3 | 1.0177 |',
    '| 4 | 1.0195 |',
    '',
    '证据：evidence:sha256:' + 'ab'.repeat(32),
  ].join('\n')
  render(<MarkdownContent>{text}</MarkdownContent>)
  const table = screen.getByRole('table')
  expect(within(table).getAllByRole('columnheader').map(cell => cell.textContent)).toEqual(['index', 'vm_pu (p.u.)'])
  const rows = within(table).getAllByRole('row').slice(1)
  expect(rows.map(row => within(row).getAllByRole('cell').map(cell => cell.textContent))).toEqual([
    ['2', '1.01'],
    ['3', '1.0177'],
    ['4', '1.0195'],
  ])
  expect(screen.getByText(/证据：evidence:sha256:ab/)).toBeTruthy()
})

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
