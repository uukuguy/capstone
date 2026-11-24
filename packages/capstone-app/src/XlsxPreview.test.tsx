import {fireEvent,render,screen} from '@testing-library/react'
import {strToU8,zipSync} from 'fflate'
import {afterEach,expect,it,vi} from 'vitest'
import {NativeFileContent} from './NativeArtifactsWorkspace'

afterEach(()=>vi.unstubAllGlobals())

it('shows a selected XLSX artifact as a read-only workbook with multiple sheets',async()=>{
  const bytes=zipSync({
    'xl/workbook.xml':strToU8('<workbook xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="电站" r:id="rId1"/><sheet name="统计" r:id="rId2"/></sheets></workbook>'),
    'xl/_rels/workbook.xml.rels':strToU8('<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/><Relationship Id="rId2" Target="/xl/worksheets/sheet2.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/></Relationships>'),
    'xl/sharedStrings.xml':strToU8('<sst><si><r><t>丰宁</t></r><r><t>电站</t></r></si></sst>'),
    'xl/worksheets/sheet1.xml':strToU8('<worksheet><sheetData><row r="1"><c r="B1" t="s"><v>0</v></c><c r="C1" t="inlineStr"><is><t>&lt;script&gt;</t></is></c></row></sheetData></worksheet>'),
    'xl/worksheets/sheet2.xml':strToU8('<worksheet><sheetData><row r="2"><c r="A2"><f>SUM(1,2)</f><v>3</v></c></row></sheetData></worksheet>'),
  })
  vi.stubGlobal('fetch',vi.fn(async()=>new Response(bytes)))
  render(<NativeFileContent name="book.xlsx" media="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" url="blob:workbook"/>)
  expect(await screen.findByRole('cell',{name:'丰宁电站'})).toBeTruthy()
  expect(screen.getByRole('cell',{name:'<script>'})).toBeTruthy()
  fireEvent.change(screen.getByLabelText('工作表'),{target:{value:'1'}})
  expect(screen.getByRole('cell',{name:'3'})).toBeTruthy()
  expect(screen.queryByText('SUM(1,2)')).toBeNull()
})

it('keeps a readable fallback for an invalid workbook',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>new Response('not a workbook')))
  render(<NativeFileContent name="invalid.xlsx" media="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" url="blob:invalid"/>)
  expect((await screen.findByRole('alert')).textContent).toContain('可下载原件')
})
