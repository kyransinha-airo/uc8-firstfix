import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The UI calls /api/...; the dev server forwards it to the backend (port 8008 by default).
// 127.0.0.1, not localhost: Node resolves localhost to ::1 first, uvicorn listens on IPv4.
const target = process.env.VITE_API_TARGET ?? 'http://127.0.0.1:8008'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3008,
    proxy: { '/api': { target, changeOrigin: true } },
  },
})
