import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Mode 'standalone' (npm run build:standalone) parses .xer files in the browser and needs
// no backend: its public dir adds the Python runtime and parser (scripts/prepare-standalone.mjs).
export default defineConfig(({ mode }) => ({
  plugins: [vue()],
  publicDir: mode === 'standalone' ? '.standalone-public' : 'public',
  worker: { format: 'es' },
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
}))
