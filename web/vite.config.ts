import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: Vite serves the UI and proxies /api to the FastAPI backend (server.py).
// Set RELIEF_API to the box's URL when developing from the Mac, e.g.
//   RELIEF_API=http://100.86.189.84:8000 npm run dev
const API = process.env.RELIEF_API || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': API } },
  build: { outDir: 'dist' },
})
