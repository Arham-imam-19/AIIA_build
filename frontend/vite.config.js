import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Inside Docker the backend is reachable as http://backend:8000.
// Running `npm run dev` on your laptop instead, it is http://localhost:8000.
const target = process.env.VITE_PROXY_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // listen on 0.0.0.0 so the port is reachable from outside Docker
    port: 5173,
    // Docker on macOS/Windows does not deliver filesystem events into the
    // container reliably, so poll for changes instead.
    watch: { usePolling: true },
    proxy: {
      // The browser calls /api/... on :5173 and Vite forwards it to FastAPI.
      // One origin for everything means no CORS surprises during the demo.
      '/api': { target, changeOrigin: true },
      // The live KPI stream. `ws: true` makes Vite forward the WebSocket
      // upgrade rather than answering it as an ordinary request.
      '/ws': { target, ws: true },
    },
  },
})
