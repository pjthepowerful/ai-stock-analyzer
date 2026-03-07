import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,   // allow other devices to connect
    port: 1420,
    strictPort: true,
  },
  build: {
    outDir: 'dist',
    target: 'esnext',
  },
})
