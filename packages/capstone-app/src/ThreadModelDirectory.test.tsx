import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ThreadModelDirectory from './ThreadModelDirectory'
import type { ThreadCatalogModel } from './threadCatalog'

afterEach(cleanup)
const models: ThreadCatalogModel[] = [
  { modelId: 'grid-a', displayName: 'Grid Alpha', implementationFamily: 'pandapower', authorityModelRef: 'a', diagramProviderId: 'a' },
  { modelId: 'pypsa/grid-b', displayName: 'Grid Beta', implementationFamily: 'pypsa', authorityModelRef: 'b', diagramProviderId: 'b' },
  { modelId: 'grid-c', displayName: 'Grid Offline', implementationFamily: 'pypsa', authorityModelRef: 'c', diagramProviderId: 'c', available: false, unavailableReason: 'worker_unavailable' },
]
const props = { models, currentModelId: 'grid-a', target: 'grid-a', disabled: false, pending: false, onTargetChange: vi.fn(), onSwitch: vi.fn() }

describe('on-demand registered model directory', () => {
  it('starts closed, focuses search on open, and restores the opener on Escape', () => {
    render(<ThreadModelDirectory {...props} />)
    expect(screen.queryByRole('listbox', { name: '目标电网模型' })).toBeNull()
    const opener = screen.getByRole('button', { name: '模型目录' })
    fireEvent.click(opener)
    expect(document.activeElement).toBe(screen.getByRole('searchbox', { name: '搜索电网模型' }))
    fireEvent.keyDown(screen.getByRole('searchbox'), { key: 'Escape' })
    expect(screen.queryByRole('searchbox')).toBeNull()
    expect(document.activeElement).toBe(opener)
  })

  it('filters registered names and IDs by family without enabling a hidden selection', () => {
    render(<ThreadModelDirectory {...props} />)
    fireEvent.click(screen.getByRole('button', { name: '模型目录' }))
    fireEvent.change(screen.getByRole('combobox', { name: '模型引擎' }), { target: { value: 'pypsa' } })
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: ' GRID-B ' } })
    expect(screen.getAllByRole('option').filter((item) => item.parentElement?.getAttribute('aria-label') === '目标电网模型').map((item) => item.getAttribute('value'))).toEqual(['pypsa/grid-b'])
    expect((screen.getByRole('button', { name: '切换模型' }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'missing' } })
    expect(screen.getByText(/没有匹配的已注册模型/)).toBeTruthy()
  })

  it.each([true, false])('keeps unavailable models disabled when controlsDisabled=%s', (disabled) => {
    render(<ThreadModelDirectory {...props} disabled={disabled} target="grid-c" />)
    fireEvent.click(screen.getByRole('button', { name: '模型目录' }))
    expect((screen.getByRole('listbox', { name: '目标电网模型' }) as HTMLSelectElement).disabled).toBe(disabled)
    expect((screen.getByRole('option', { name: /Grid Offline.*worker_unavailable/ }) as HTMLOptionElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: '切换模型' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('opens only the explicitly selected available model through the existing callback', () => {
    const onSwitch = vi.fn()
    const { rerender } = render(<ThreadModelDirectory {...props} onSwitch={onSwitch} />)
    fireEvent.click(screen.getByRole('button', { name: '模型目录' }))
    fireEvent.change(screen.getByRole('listbox', { name: '目标电网模型' }), { target: { value: 'pypsa/grid-b' } })
    expect(props.onTargetChange).toHaveBeenCalledWith('pypsa/grid-b')
    expect(onSwitch).not.toHaveBeenCalled()
    rerender(<ThreadModelDirectory {...props} target="pypsa/grid-b" onSwitch={onSwitch} />)
    fireEvent.click(screen.getByRole('button', { name: '切换模型' }))
    expect(onSwitch).toHaveBeenCalledTimes(1)
    rerender(<ThreadModelDirectory {...props} currentModelId="pypsa/grid-b" target="pypsa/grid-b" onSwitch={onSwitch} />)
    expect(screen.queryByRole('searchbox')).toBeNull()
  })
})
