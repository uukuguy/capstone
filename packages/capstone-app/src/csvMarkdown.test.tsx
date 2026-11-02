import {expect,it} from 'vitest'
import {render,screen,within} from '@testing-library/react'
import {NativeFileContent} from './NativeArtifactsWorkspace'
it('renders literal CSV cells as a markdown table without changing source text',()=>{
  const text='\uFEFF名称,说明,值\r\n北京,"逗号,引号""与\n换行",001\r\n天津,**字面**|<img>,=1+2';
  render(<NativeFileContent name="data.csv" media="text/csv" text={text}/>);
  const table=within(screen.getByRole('table'));
  expect(table.getByRole('columnheader',{name:'名称'})).toBeTruthy();
  expect(table.getByRole('cell',{name:'001'})).toBeTruthy();
  expect(table.getByRole('cell',{name:'**字面**|<img>'})).toBeTruthy();
  expect(table.getByRole('cell',{name:'=1+2'})).toBeTruthy();
  expect(table.getAllByRole('row')).toHaveLength(3);
});
