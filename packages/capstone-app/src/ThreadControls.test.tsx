import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import ThreadControls from './ThreadControls'
import { parseThreadCatalog } from './threadCatalog'

afterEach(cleanup)
const profiles = [
  { profile_id: 'pandapower-static-analysis', profile_version: '1.0.1', display_name: 'Pandapower Static Analysis', implementation_families: ['pandapower'] },
  { profile_id: 'alternative-analysis', profile_version: '2.0', display_name: '另一组分析工具', implementation_families: ['pandapower'] },
  { profile_id: 'pypsa-business-cases', profile_version: '1.0.0', display_name: 'PyPSA Business Cases', implementation_families: ['pypsa'] },
]
const catalog = parseThreadCatalog({ schema: 'capstone-thread-catalog/1', models: [], profiles })
const selected = [{ profileId: 'pandapower-static-analysis', profileVersion: '1.0.1' }]
const props = { catalog, activeFamily: 'pandapower', activeProfiles: selected, pendingProfileSelection: undefined,
  pendingModel: undefined, disabled: false, historyActions: <span>历史回答</span> }

it('saves a compatible tool-group change with exact profile references', () => {
  const onProfileSelection = vi.fn()
  render(<ThreadControls {...props} onProfileSelection={onProfileSelection} />)
  fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
  expect((screen.getByRole('checkbox', { name: 'PyPSA 电网分析' }) as HTMLInputElement).disabled).toBe(true)
  expect(screen.getByText('需 PyPSA 模型')).toBeTruthy()
  expect(screen.queryByRole('button', { name: '保存工具选择' })).toBeNull()
  fireEvent.click(screen.getByRole('checkbox', { name: '另一组分析工具' }))
  fireEvent.click(screen.getByRole('checkbox', { name: 'pandapower 静态分析' }))
  fireEvent.click(screen.getByRole('button', { name: '保存工具选择' }))
  expect(onProfileSelection).toHaveBeenCalledExactlyOnceWith([{ profileId: 'alternative-analysis', profileVersion: '2.0' }])
  expect(screen.queryByRole('checkbox')).toBeNull()
})

it('shows PyPSA as grid-analysis tools and prevents changes during a model switch', () => {
  render(<ThreadControls {...props} activeFamily="pypsa" activeProfiles={[{ profileId: 'pypsa-business-cases', profileVersion: '1.0.0' }]}
    pendingModel="next-model" onProfileSelection={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
  expect((screen.getByRole('checkbox', { name: 'PyPSA 电网分析' }) as HTMLInputElement).disabled).toBe(true)
  expect(screen.queryByText('PyPSA Business Cases')).toBeNull()
})
