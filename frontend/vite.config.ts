import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The dev server proxies /api to the FastAPI backend so the browser sees one origin.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // File watching can stall in sandboxed or restricted shells. ROAMWISE_NO_WATCH=1 turns it
    // off (no hot reload: restart the server to pick up changes).
    watch: process.env.ROAMWISE_NO_WATCH ? null : undefined,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
