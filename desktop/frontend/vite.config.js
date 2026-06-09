import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { execSync } from 'child_process'

let commit = 'dev'
try {
  const out = execSync('git rev-parse --short HEAD', { stdio: ['pipe', 'pipe', 'ignore'] }).toString().trim()
  if (out) commit = out
} catch (e) {
  const sha = process.env.VERCEL_GIT_COMMIT_SHA
  if (sha) commit = sha.slice(0, 7)
}
// guarantee a safe, simple token (defensive — avoids any chance of malformed define)
commit = String(commit).replace(/[^a-zA-Z0-9]/g, '').slice(0, 12) || 'dev'

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
