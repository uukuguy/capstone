import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

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
    plugins: [react()],
    test: { environment: 'jsdom' },
    server: {
      proxy: { '/api': localApiProxy, '/health': localApiProxy },
    },
  }
})
