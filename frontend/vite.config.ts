import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

const apiTarget = process.env.LUMA_API_PROXY || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  build: { rollupOptions: { output: { manualChunks: { charts: ['recharts'] } } } },
  server: { port: 5173, strictPort: true, proxy: { '/api': apiTarget, '/health': apiTarget } },
  test: { environment: 'jsdom', setupFiles: './src/test/setup.ts', css: false },
})
