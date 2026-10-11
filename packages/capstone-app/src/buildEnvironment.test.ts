import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import type { ConfigEnv, UserConfig } from 'vite'
import config from '../vite.config'

let directory: string
const original = process.cwd()
const revision = 'a'.repeat(40)
const origin = 'https://api.example.com'
const receipt = { schema: 'capstone-app-environment/1', environment: 'cloud-demo', source_revision: revision, api_origin: origin }

beforeEach(() => {
  directory = mkdtempSync(join(tmpdir(), 'capstone-app-identity-'))
  process.chdir(directory)
  writeFileSync('package.json', '{"version":"0.1.0"}')
  writeFileSync('build-revision.txt', revision)
  vi.stubEnv('VITE_API_ORIGIN', '')
  vi.stubEnv('CAPSTONE_APP_ENVIRONMENT', '')
})
afterEach(() => { process.chdir(original); rmSync(directory, { recursive: true }); vi.unstubAllEnvs() })

function identity(mode = 'production') {
  const factory = config as (env: ConfigEnv) => UserConfig
  const document = factory({ mode, command: 'build' })
  return JSON.parse(document.define!.__CAPSTONE_BUILD__ as string)
}

it('uses unknown without explicit configuration rather than inferring from origins or ports', () => {
  vi.stubEnv('CAPSTONE_API_PROXY_TARGET', 'http://127.0.0.1:18767')
  expect(identity('development').environment).toBeNull()
  expect(identity().environment).toBeNull()
})

it.each(['local-dev', 'local-demo'])('selects explicit local runtime environment %s', environment => {
  vi.stubEnv('CAPSTONE_APP_ENVIRONMENT', environment)
  expect(identity('development').environment).toBe(environment)
})

it.each(['cloud-dev', 'cloud-demo'])('binds hosted %s to source and API origin receipts', environment => {
  vi.stubEnv('VITE_API_ORIGIN', origin)
  writeFileSync('build-environment.json', JSON.stringify({ ...receipt, environment }))
  expect(identity().environment).toBe(environment)
})

it.each([
  { ...receipt, source_revision: 'b'.repeat(40) },
  { ...receipt, api_origin: 'https://another.example.com' },
  { ...receipt, environment: 'local-demo' },
  { ...receipt, unexpected: 'private' },
])('rejects mismatched or invalid hosted receipt %j', document => {
  vi.stubEnv('VITE_API_ORIGIN', origin)
  writeFileSync('build-environment.json', JSON.stringify(document))
  expect(() => identity()).toThrow()
})

it('rejects a hosted API origin without a receipt', () => {
  vi.stubEnv('VITE_API_ORIGIN', origin)
  expect(() => identity()).toThrow()
})

it('rejects cloud labels supplied as local runtime settings', () => {
  vi.stubEnv('CAPSTONE_APP_ENVIRONMENT', 'cloud-demo')
  expect(() => identity('development')).toThrow()
})
