import {afterEach,expect,it} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import ResearchProgressSummary from './ResearchProgressSummary'
afterEach(cleanup)
it('shows business progress and limitations without exposing internal tool records',()=>{
  render(<ResearchProgressSummary nodes={[{id:'load',purpose:'分析负荷变化',phase:'success',applicability:'current'},{id:'weather',purpose:'分析气温和降水',phase:'executing',applicability:'current'},{id:'ppt',purpose:'生成总结PPT',phase:'pending',applicability:'current'}]} limitations={['缺少本年度数据']} running/>)
  expect(screen.getByText('已完成 1 / 3 项')).toBeTruthy()
  expect(screen.getByText('分析气温和降水')).toBeTruthy()
  expect(screen.getByText('缺少本年度数据')).toBeTruthy()
  expect(screen.queryByText('正在生成总结PPT')).toBeNull()
})
it('does not treat a returned or interrupted task as completed delivery',()=>{
  const {rerender}=render(<ResearchProgressSummary nodes={[{id:'one',purpose:'研究',phase:'executed',applicability:'current'}]} limitations={[]} running/>)
  expect(screen.getByText('研究结果已返回，等待接收')).toBeTruthy()
  rerender(<ResearchProgressSummary nodes={[{id:'one',purpose:'研究',phase:'executing',applicability:'current'}]} limitations={[]} running={false}/>)
  expect(screen.queryByText('正在进行')).toBeNull()
})
