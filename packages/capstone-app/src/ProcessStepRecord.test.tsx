import { afterEach, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import ProcessStepRecord from './ProcessStepRecord'

afterEach(() => { cleanup(); localStorage.clear() })
it('folds the entire body by default while keeping metrics visible', () => {
  render(<ProcessStepRecord id="one" title="Generic task" storageKey="work" heading={<span>Tools 2</span>}>Task result</ProcessStepRecord>)
  expect(screen.getByText('Tools 2')).toBeVisible()
  expect(screen.getByText('Task result')).not.toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '展开步骤：Generic task' }))
  expect(screen.getByText('Task result')).toBeVisible()
})
it('keeps a bounded result summary visible while the details are folded', () => {
  render(<ProcessStepRecord id="summary" title="Task" storageKey="summary" heading={<span>Metrics</span>} resultSummary={'Actual saved finding. '.repeat(40)}>Full result</ProcessStepRecord>)
  expect(screen.getByText(/Actual saved finding/)).toBeVisible()
  expect(screen.getByText(/Actual saved finding/).textContent!.length).toBeLessThanOrEqual(181)
  expect(screen.getByText('Full result')).not.toBeVisible()
})
it('keeps explicit manual choices across remounts and separates reader preferences', () => {
  const props = { id: 'one', title: 'Task', storageKey: 'reader', heading: <span>Metrics</span>, defaultExpanded: true }
  const view = render(<ProcessStepRecord {...props}>Content</ProcessStepRecord>)
  expect(screen.getByText('Content')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '折叠步骤：Task' }))
  view.unmount()
  render(<ProcessStepRecord {...props}>Content</ProcessStepRecord>)
  expect(screen.getByText('Content')).not.toBeVisible()
})
it('applies bulk commands once and preserves subsequent manual choices on updates', () => {
  const props = { id: 'one', title: 'Task', storageKey: 'bulk', heading: <span>Metrics</span> }
  const command = { open: true, revision: 1 }
  const view = render(<ProcessStepRecord {...props} foldCommand={command}>Content</ProcessStepRecord>)
  expect(screen.getByText('Content')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '折叠步骤：Task' }))
  view.rerender(<ProcessStepRecord {...props} foldCommand={command}>Updated</ProcessStepRecord>)
  expect(screen.getByText('Updated')).not.toBeVisible()
  view.unmount()
  render(<ProcessStepRecord {...props} foldCommand={command}>Restored</ProcessStepRecord>)
  expect(screen.getByText('Restored')).not.toBeVisible()
})
