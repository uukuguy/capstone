import { afterEach, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import AnswerDetailSheet from './AnswerDetailSheet'

afterEach(cleanup)

it('opens an answer-scoped detail sheet and restores focus and body scrolling on Escape', () => {
  function Example() {
    const [open,setOpen]=useState(false)
    return <><button onClick={()=>setOpen(true)}>查看来源</button>{open && <AnswerDetailSheet title="来源与记录" answerLabel="检查当前模型" onClose={()=>setOpen(false)}><p>真实来源记录</p></AnswerDetailSheet>}</>
  }
  render(<Example />)
  const trigger=screen.getByRole('button',{name:'查看来源'})
  trigger.focus(); fireEvent.click(trigger)
  const dialog=screen.getByRole('dialog',{name:'来源与记录'})
  expect(dialog.textContent).toContain('检查当前模型')
  expect(document.body.style.overflow).toBe('hidden')
  expect(document.activeElement).toBe(screen.getByRole('button',{name:'关闭来源与记录'}))
  fireEvent.keyDown(dialog,{key:'Escape'})
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(document.activeElement).toBe(trigger)
  expect(document.body.style.overflow).toBe('')
})
