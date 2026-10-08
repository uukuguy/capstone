import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { execFileSync } from 'node:child_process'
import { readFileSync, existsSync } from 'node:fs'

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
    define: { __CAPSTONE_BUILD__: JSON.stringify({ version: JSON.parse(readFileSync('package.json', 'utf8')).version, revision: buildRevision() }) },
    plugins: [react()],
    test: { environment: 'jsdom', setupFiles: ['./src/testSetup.ts'] },
    server: {
      proxy: { '/api': localApiProxy, '/health': localApiProxy },
    },
  }
})
