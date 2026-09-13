import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Bind all local interfaces so localhost resolves on IPv4 or IPv6.
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.AP2WEB_API_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
