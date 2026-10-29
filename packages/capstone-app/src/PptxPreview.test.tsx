import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import PptxPreview from './PptxPreview'

vi.mock('@office-kit/pptx',()=>({loadPresentation:vi.fn(async()=>({})),getSlides:()=>[{id:1},{id:2}]}))
vi.mock('@office-kit/pptx-preview',()=>({renderSlideToSvg:(_p:unknown,s:{id:number})=>`<svg xmlns="http://www.w3.org/2000/svg"><text>${s.id}</text></svg>`}))
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('shows slides locally and provides bounded page navigation',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,arrayBuffer:async()=>new ArrayBuffer(4)})))
  vi.spyOn(URL,'createObjectURL').mockReturnValue('blob:slide')
  vi.spyOn(URL,'revokeObjectURL').mockImplementation(()=>{})
  render(<PptxPreview name="总结.pptx" url="blob:verified-file"/> )
  await screen.findByAltText('总结.pptx · 第 1 页')
  expect((screen.getByRole('button',{name:'上一页'}) as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(screen.getByRole('button',{name:'下一页'}))
  await screen.findByAltText('总结.pptx · 第 2 页')
  expect((screen.getByRole('button',{name:'下一页'}) as HTMLButtonElement).disabled).toBe(true)
})
it('does not fetch an external document URL',async()=>{
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch)
  render(<PptxPreview name="总结.pptx" url="https://example.com/file.pptx"/> )
  await screen.findByRole('alert')
  expect(fetch).not.toHaveBeenCalled()
})
