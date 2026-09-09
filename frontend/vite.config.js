import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// A per-build id, used to cache-bust data.json. GitHub Pages serves every
// file with a 10-minute cache header and browsers reuse a plain ./data.json
// URL for far longer, so viewers kept seeing last week's numbers after a
// publish. Every push rebuilds, so the id changes with every deploy.
const BUILD_ID = Date.now().toString(36)

export default defineConfig({
  base: './',
  define: { __BUILD_ID__: JSON.stringify(BUILD_ID) },
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    hmr: {
      host: 'localhost',
      port: 5173
    }
  }
})
