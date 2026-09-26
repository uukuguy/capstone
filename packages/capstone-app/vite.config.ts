import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Keep the API on loopback when the dev App is shared on a local network.
const localApiProxy = {
  target: 'http://127.0.0.1:8767',
  changeOrigin: true,
  headers: { Origin: 'http://127.0.0.1:5173' },
}

export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom' },
  server: {
    proxy: { '/api': localApiProxy, '/health': localApiProxy },
  },
})
