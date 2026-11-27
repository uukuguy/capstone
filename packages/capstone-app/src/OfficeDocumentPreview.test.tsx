import {cleanup,render,screen} from '@testing-library/react'
import {strToU8,zipSync} from 'fflate'
import {afterEach,expect,it,vi} from 'vitest'
import {NativeFileContent,nativePreviewMedia} from './NativeArtifactsWorkspace'

afterEach(()=>{cleanup();vi.unstubAllGlobals()})

it('previews a downloaded DOCX with generic MIME as read-only paragraphs and tables',async()=>{
  const archive=zipSync({'word/document.xml':strToU8('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>核验报告</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>&lt;script&gt;</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')})
  vi.stubGlobal('fetch',vi.fn(async()=>new Response(archive)))
  render(<NativeFileContent name="report.docx" media={nativePreviewMedia('report.docx','application/octet-stream')} url="blob:report"/>)
  expect(await screen.findByText('核验报告')).toBeTruthy()
  expect(screen.getByRole('cell',{name:'<script>'})).toBeTruthy()
})

it.each([
  ['sample.odt','text','<t:p>文档正文</t:p>','文档正文'],
  ['sample.ods','spreadsheet','<s:table s:name="数据"><s:table-row><s:table-cell><t:p>单元格</t:p></s:table-cell></s:table-row></s:table>','单元格'],
  ['sample.odp','presentation','<d:page d:name="概况"><d:frame><d:text-box><t:p>幻灯片正文</t:p></d:text-box></d:frame></d:page>','幻灯片正文'],
])('previews %s content without loading linked resources',async(name,body,xml,expected)=>{
  const archive=zipSync({'content.xml':strToU8(`<o:document-content xmlns:o="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:s="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:t="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:d="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"><o:body><o:${body}>${xml}</o:${body}></o:body></o:document-content>`)})
  const fetch=vi.fn(async()=>new Response(archive))
  vi.stubGlobal('fetch',fetch)
  render(<NativeFileContent name={name} media={nativePreviewMedia(name,'application/octet-stream')} url="blob:sample"/>)
  expect(await screen.findByText(expected)).toBeTruthy()
  expect(fetch).toHaveBeenCalledTimes(1)
})

it('previews TSV as a table',()=>{
  render(<NativeFileContent name="data.tsv" media={nativePreviewMedia('data.tsv','application/octet-stream')} text={'地区\t功率\n北京\t100'}/>)
  expect(screen.getByRole('columnheader',{name:'功率'})).toBeTruthy()
  expect(screen.getByRole('cell',{name:'100'})).toBeTruthy()
})

it('does not fetch a non-Blob source',async()=>{
  const fetch=vi.fn()
  vi.stubGlobal('fetch',fetch)
  render(<NativeFileContent name="report.docx" media={nativePreviewMedia('report.docx',null)} url="https://example.test/report.docx"/>)
  expect((await screen.findByRole('alert')).textContent).toContain('下载原件')
  expect(fetch).not.toHaveBeenCalled()
})
