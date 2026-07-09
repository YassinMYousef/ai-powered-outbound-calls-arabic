import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Backend API — run uvicorn on :8000 (see backend/README quickstart)
      '/api': 'http://localhost:8000',
    },
  },
})
