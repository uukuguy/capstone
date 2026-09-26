import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom' },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8767', '/health': 'http://127.0.0.1:8767' },
  },
})
