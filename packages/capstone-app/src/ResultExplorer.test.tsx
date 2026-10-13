import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import ResultExplorer from './ResultExplorer'
import type { ResultProjection } from './threadProtocol'
afterEach(cleanup)
describe('result explorer', () => {
  it('opens outside the message layout and shows one result and table at a time', () => {
    const projection = { resultId: 'one', modelId: 'ieee39', status: 'completed', source: { capabilityId: 'opf.ac' }, summary: [],
      tables: [{ tableId: 'lines', title: '线路负载率', rows: [] }, { tableId: 'prices', title: '节点电价', rows: [] }] } as unknown as ResultProjection
    const close = vi.fn()
    const { container } = render(<ResultExplorer projections={[projection]} failures={[]} onClose={close}
      renderResult={(_, tableId) => <span>{tableId}</span>} />)
    expect(container.querySelector('dialog')).toBeNull()
    expect(screen.getByRole('dialog', { name: '计算结果' })).toBeTruthy()
    expect(screen.getByText('lines')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /节点电价/ }))
    expect(screen.getByText('prices')).toBeTruthy()
    expect(screen.queryByText('lines')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '关闭计算结果' }))
    expect(close).toHaveBeenCalledOnce()
  })
})
