import {afterEach,it,expect,vi} from 'vitest'
import {cleanup,render,screen,fireEvent,waitFor} from '@testing-library/react'
import TaskDeliveriesWorkspace,{parseDeliveries} from './TaskDeliveriesWorkspace'
import type {CapstoneThreadClient} from './threadClient'
import type {NativeArtifact} from './nativeArtifacts'

afterEach(cleanup)
const source={productId:'process_attempt_1',threadId:'thr_one',attemptId:'attempt_1',workId:null,instruction:'检查过载',status:'failed',eventSeq:9,occurredAt:'2026-10-17T00:00:00Z',failureCode:null,modelContext:null}
const delivery={scope:'task',thread_id:'thr_one',artifact_id:`delivery_${'a'.repeat(32)}`,revision:1,title:'分析材料',work_id:null,request:{request_id:'request_one',scope:'保留失败与缺口'},supporting_process_ids:[source.productId]}
const page={schema:'capstone-deliveries/1',thread_id:'thr_one',deliveries:[],has_more:false,next_before_event_seq:null}
it('keeps an exact delivery request on network retry and previews persisted bytes without ending the session',async()=>{
  const publish=vi.fn().mockRejectedValueOnce(new Error('连接中断')).mockResolvedValue({status:'accepted',target:{delivery}})
  const products=vi.fn().mockResolvedValueOnce({products:[],hasMore:true,nextBefore:20}).mockResolvedValue({products:[source],hasMore:false,nextBefore:1})
  const client={deliveries:vi.fn().mockResolvedValue(page),processProducts:products,publishDelivery:publish,deliveryContent:vi.fn().mockResolvedValue('# 已保存材料\n\n失败原因与下一步。')} as unknown as CapstoneThreadClient
  const completed=vi.fn()
  render(<TaskDeliveriesWorkspace client={client} threadId="thr_one" revision={9} onPublished={completed}/>)
  fireEvent.click(screen.getByRole('button',{name:'生成交付材料'}))
  await screen.findByText('检查过载')
  expect(products.mock.calls[1][1]).toBe(20)
  fireEvent.change(screen.getByLabelText('交付名称'),{target:{value:'分析材料'}})
  fireEvent.change(screen.getByLabelText('范围与用途'),{target:{value:'保留失败与缺口'}})
  fireEvent.click(screen.getByRole('checkbox'))
  fireEvent.click(screen.getByRole('button',{name:'生成 Markdown'}))
  await screen.findByText('连接中断')
  fireEvent.click(screen.getByRole('button',{name:'重试同一交付请求'}))
  await screen.findByRole('heading',{name:'已保存材料'})
  expect(publish.mock.calls[0]).toEqual(publish.mock.calls[1])
  expect(publish.mock.calls[0][1]).toMatchObject({expected_revision:0,trigger_attempt_id:'attempt_1',supporting_process_ids:[source.productId]})
  await waitFor(()=>expect(completed).toHaveBeenCalledTimes(1))
  expect(screen.getByRole('button',{name:'生成交付材料'})).toBeTruthy()
})
it('rejects an instruction product or foreign thread from the task delivery catalog',()=>{
  expect(()=>parseDeliveries({...page,deliveries:[{...delivery,scope:'instruction'}]},'thr_one')).toThrow()
  expect(()=>parseDeliveries({...page,deliveries:[{...delivery,thread_id:'thr_other'}]},'thr_one')).toThrow()
})

it('requires explicit adoption of the original file and can create a new version of an existing delivery',async()=>{
  const native={thread_id:'thr_one',attempt_id:'attempt_2',work_id:null,artifact_id:`file-${'b'.repeat(16)}-${'c'.repeat(64)}`,file_name:'revised.csv',source_status:'failed'} as NativeArtifact
  const publish=vi.fn().mockResolvedValue({status:'accepted',target:{delivery:{...delivery,revision:2,format:'native-file',file_name:'revised.csv',media_type:'text/csv',byte_size:4,content_digest:'c'.repeat(64),generation_status:'failed'}}})
  const client={deliveries:vi.fn().mockResolvedValue({...page,deliveries:[delivery]}),processProducts:vi.fn().mockResolvedValue({products:[],hasMore:false,nextBefore:1}),publishDelivery:publish,supportsDeliveryFiles:true,deliveryFile:vi.fn().mockResolvedValue(new TextEncoder().encode('a,1\n'))} as unknown as CapstoneThreadClient
  render(<TaskDeliveriesWorkspace client={client} threadId="thr_one" revision={12} requestedArtifact={native}/>)
  expect(screen.getByText('可采用指令生成的已保存文件，或将选定过程与结果整理为 Markdown。交付可继续修订，会话仍可继续。')).toBeTruthy()
  await screen.findByRole('option',{name:'修订：分析材料 · v1'})
  expect(publish).not.toHaveBeenCalled()
  expect(screen.getByText(/来源执行未完成/)).toBeTruthy()
  fireEvent.change(screen.getByLabelText('交付版本'),{target:{value:'request_one'}})
  fireEvent.click(screen.getByRole('button',{name:'生成新版本'}))
  await screen.findByText('a,1')
  expect(publish.mock.calls[0][1]).toMatchObject({format:'native-file',request_id:'request_one',expected_revision:1,trigger_attempt_id:'attempt_2',source_artifact:{attempt_id:'attempt_2',artifact_id:native.artifact_id},supporting_process_ids:['process_attempt_2']})
})
