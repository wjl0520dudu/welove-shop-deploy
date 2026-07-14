import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// admin-web dev-server 代理 /api → gateway :8080
// 生产由 nginx 同源反代
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3100,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
})
