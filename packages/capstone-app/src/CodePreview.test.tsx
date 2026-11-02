import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import CodePreview from './CodePreview'
import {nativePreviewMedia} from './NativeArtifactsWorkspace'

afterEach(cleanup)
it('recognizes SQL and source filenames as text without altering the stored media contract',()=>{
  expect(nativePreviewMedia('query.sql','application/sql')).toBe('text/plain')
  expect(nativePreviewMedia('analysis.py','application/octet-stream')).toBe('text/plain')
  expect(nativePreviewMedia('image.svg','application/octet-stream')).toBe('image/svg+xml')
})
it('renders highlighted SQL as escaped React text with a language selector',()=>{
  const text="SELECT '<script>alert(1)</script>' AS sample;"
  const {container}=render(<CodePreview name="query.sql" text={text}/>)
  expect(container.querySelector('code')?.textContent).toBe(text)
  expect(container.querySelector('.hljs-keyword')).toBeTruthy()
  expect(container.querySelector('script')).toBeNull()
  expect(screen.getByRole('combobox',{name:'代码语言'})).toBeTruthy()
  fireEvent.change(screen.getByRole('combobox',{name:'代码语言'}),{target:{value:'plaintext'}})
  expect(container.querySelector('code')?.textContent).toBe(text)
})
