import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { execFileSync } from 'node:child_process'
import { readFileSync, existsSync } from 'node:fs'
import type { AppEnvironment } from './src/appBuild'

// Release archives carry a non-secret source receipt. Local development reads Git.
function buildRevision() {
  if (existsSync('build-revision.txt')) {
    const revision = readFileSync('build-revision.txt', 'utf8').trim()
    if (revision !== 'development') {
      if (!/^[a-f0-9]{40}$/.test(revision)) throw new Error('Invalid App build revision')
      return revision
    }
  }
  try { return execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim() }
  catch { return '' }
}

function publicOrigin(value: unknown): string {
  if (typeof value !== 'string') throw new Error('Invalid App API origin')
  const origin = value.replace(/\/$/, '')
  let url: URL
  try { url = new URL(origin) }
  catch { throw new Error('Invalid App API origin') }
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.origin !== origin) {
    throw new Error('Invalid App API origin')
  }
  return origin
}

function buildEnvironment(env: Record<string, string>, revision: string, development: boolean): AppEnvironment | null {
  if (existsSync('build-environment.json')) {
    const receipt = JSON.parse(readFileSync('build-environment.json', 'utf8'))
    if (!receipt || typeof receipt !== 'object' || Object.keys(receipt).sort().join(',') !== 'api_origin,environment,schema,source_revision' ||
        receipt.schema !== 'capstone-app-environment/1' || !['cloud-dev', 'cloud-demo'].includes(receipt.environment) ||
        !/^[a-f0-9]{40}$/.test(receipt.source_revision) || receipt.source_revision !== revision ||
        publicOrigin(receipt.api_origin) !== publicOrigin(env.VITE_API_ORIGIN) || development) {
      throw new Error('App environment receipt does not match its selected deployment')
    }
    return receipt.environment
  }
  if (development) {
    const environment = env.CAPSTONE_APP_ENVIRONMENT || null
    if (environment !== null && environment !== 'local-dev' && environment !== 'local-demo') {
      throw new Error('Invalid local App environment')
    }
    return environment
  }
  if (env.VITE_API_ORIGIN) throw new Error('Hosted App environment receipt is required')
  return null
}

function buildIdentity(env: Record<string, string>, development = false) {
  let dirty = false
  if (development) {
    try { dirty = Boolean(execFileSync('git', ['status', '--porcelain', '--untracked-files=normal', '--', 'packages', 'configs', 'deploy', 'Dockerfile'], { cwd: '../..', encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim()) }
    catch { /* A source-only checkout has no Git worktree. */ }
  }
  const revision = buildRevision()
  return { version: JSON.parse(readFileSync('package.json', 'utf8')).version, revision, dirty,
    environment: buildEnvironment(env, revision, development) }
}

export default defineConfig(({ mode }) => {
  // Keep the API behind Vite's same-origin proxy. This lets a phone on the LAN
  // use the local UI without exposing the local operator API or requiring CORS
  // changes for every temporary LAN address.
  const env = loadEnv(mode, '.', '')
  const apiProxyTarget = env.CAPSTONE_API_PROXY_TARGET || 'http://127.0.0.1:8767'
  // The local API allowlist contains the App origin, not the API's own
  // loopback address. Keep the proxy same-origin for desktop and LAN clients;
  // hosted deployments override both values explicitly at startup.
  const apiProxyOrigin = env.CAPSTONE_API_PROXY_ORIGIN || 'http://127.0.0.1:5173'
  const localApiProxy = {
    target: apiProxyTarget,
    changeOrigin: true,
    headers: { Origin: apiProxyOrigin },
  }
  return {
    define: { __CAPSTONE_BUILD__: JSON.stringify(buildIdentity(env, mode === 'development')) },
    plugins: [react(), {
      name: 'capstone-local-build-identity',
      configureServer(server) {
        server.middlewares.use('/__capstone-build', (_request, response) => {
          response.setHeader('Content-Type', 'application/json')
          response.setHeader('Cache-Control', 'no-store')
          response.end(JSON.stringify(buildIdentity(env, true)))
        })
      },
    }],
    test: { environment: 'jsdom', setupFiles: ['./src/testSetup.ts'] },
    server: {
      proxy: { '/api': localApiProxy, '/health': localApiProxy },
    },
  }
})
