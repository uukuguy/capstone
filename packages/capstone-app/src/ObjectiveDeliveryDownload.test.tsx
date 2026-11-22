import {expect,it} from 'vitest'
import {objectiveDeliveryDocument} from './ObjectiveDeliveryDownload'

it('exports the saved whole-objective answer and keeps each criterion verdict',()=>{
  const document=objectiveDeliveryDocument({
    title:'Mission 整体交付', objective:'保存并核对两份文件', revision:4,
    status:'部分交付', summary:'已核对第一份文件。',
    criteria:[
      {label:'核对首份文件',status:'已满足',references:['source.csv · SHA-256 1234']},
      {label:'核对第二份文件',status:'待核实',explanation:'尚未收到文件。'},
    ],
  })
  expect(document).toContain('修订 4 · 部分交付')
  expect(document).toContain('## 整体答复\n\n已核对第一份文件。')
  expect(document).toContain('核验依据\n- source.csv · SHA-256 1234')
  expect(document).toContain('- 核对第二份文件 · 待核实\n\n尚未收到文件。')
})
