import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync, existsSync } from 'node:fs'
import { localBuildIdentity } from './src/dev/localBuildIdentity'

// Release archives carry a non-secret source receipt. Local development reads Git.
function buildRevision() {
  if (existsSync('build-revision.txt')) {
    const revision = readFileSync('build-revision.txt', 'utf8').trim()
    if (revision !== 'development') {
      if (!/^[a-f0-9]{40}$/.test(revision)) throw new Error('Invalid App build revision')
      return revision
    }
  }
  try { return localBuildIdentity('../..').revision }
  catch { return '' }
}

function buildIdentity(development = false) {
  let local: { dirty: boolean; repositoryRevision?: string } = { dirty: false }
  if (development) {
    try { local = localBuildIdentity('../..') }
    catch { /* A source-only checkout has no Git worktree. */ }
  }
  return { version: JSON.parse(readFileSync('package.json', 'utf8')).version, revision: buildRevision(), ...local }
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
    define: { __CAPSTONE_BUILD__: JSON.stringify(buildIdentity(mode === 'development')) },
    plugins: [react(), {
      name: 'capstone-local-build-identity',
      transformIndexHtml() {
        if (mode !== 'development') return
        return [{ tag: 'script', attrs: { type: 'module' }, injectTo: 'body', children: `
          document.addEventListener('mouseover', async event => {
            const label = event.target.closest?.('.app-version');
            if (!label) return;
            try {
              const response = await fetch('/__capstone-build');
              if (!response.ok) return;
              const build = await response.json();
              label.title = '产品版本：' + build.revision + (build.dirty ? '（含未提交修改）' : '')
                + '\\n仓库提交：' + build.repositoryRevision;
            } catch {}
          });
        ` }]
      },
      configureServer(server) {
        server.middlewares.use('/__capstone-build', (_request, response) => {
          response.setHeader('Content-Type', 'application/json')
          response.setHeader('Cache-Control', 'no-store')
          response.end(JSON.stringify(buildIdentity(true)))
        })
      },
    }],
    test: { environment: 'jsdom', setupFiles: ['./src/testSetup.ts'] },
    server: {
      proxy: { '/api': localApiProxy, '/health': localApiProxy },
    },
  }
})
