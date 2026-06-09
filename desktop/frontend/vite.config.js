import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { execSync } from 'child_process'

let commit = 'dev'
try {
  commit = execSync('git rev-parse --short HEAD').toString().trim()
} catch (e) {
  commit = process.env.VERCEL_GIT_COMMIT_SHA?.slice(0, 7) || 'dev'
}

export default defineConfig({
  plugins: [react()],
  define: {
    __BUILD_COMMIT__: JSON.stringify(commit),
  },
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
