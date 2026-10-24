import { expect, it, vi } from 'vitest'
import { HttpThreadTransport, isThreadVersionError } from './threadHttpTransport'
import { parseThreadDescriptor } from './threadManagement'

it('accepts absent model identity only for a v2 work descriptor', () => {
  const row = { thread_id: 'thr_work', model_id: null, implementation_family: null,
    created_at: '2026-10-16T12:00:00Z', archived: false, last_event_seq: 0, minimum_protocol_version: 2 }
  expect(parseThreadDescriptor(row).modelId).toBeNull()
  expect(() => parseThreadDescriptor({ ...row, minimum_protocol_version: 1 })).toThrow()
})
it('preserves valid host update timestamps and permits older descriptors without them',()=>{
  const row={thread_id:'thr_work',model_id:null,implementation_family:null,created_at:'2026-10-16T12:00:00Z',archived:false,last_event_seq:1,minimum_protocol_version:2}
  expect(parseThreadDescriptor({...row,updated_at:'2026-10-25T01:02:03Z'}).updatedAt).toBe('2026-10-25T01:02:03Z')
  expect(parseThreadDescriptor(row).updatedAt).toBeUndefined()
  expect(()=>parseThreadDescriptor({...row,updated_at:'invalid'})).toThrow()
})

it('explicitly negotiates v2 for model-free creation without retrying a write', async () => {
  const fetcher = vi.fn(async (_url: string | URL | Request, _init?: RequestInit) => new Response('{}', { headers: { 'Capstone-Thread-Version': '2' } }))
  const transport = new HttpThreadTransport('', '', fetcher, '/api/v1/threads', '2')
  await transport.createWorkThread()
  expect(fetcher).toHaveBeenCalledTimes(1)
  expect(fetcher.mock.calls[0]?.[1]).toMatchObject({ method: 'POST', headers: { 'Capstone-Thread-Version': '2' } })
  expect(JSON.parse(String(fetcher.mock.calls[0]?.[1]?.body))).not.toHaveProperty('model_id', 'ieee39')
})

it('surfaces an upgrade during an open stream without emitting a fake ledger event', async () => {
  const fetcher = vi.fn(async () => new Response('event: protocol_upgrade_required\ndata: {"error":"protocol_upgrade_required","minimum_protocol_version":2}\n\n',
    { headers: { 'Capstone-Thread-Version': '1' } }))
  const transport = new HttpThreadTransport('', '', fetcher)
  try {
    for await (const _event of transport.streamEvents('thr_work', 0)) throw new Error('unexpected ledger event')
    throw new Error('stream should require upgrade')
  } catch (error) { expect(isThreadVersionError(error)).toBe(true) }
})
