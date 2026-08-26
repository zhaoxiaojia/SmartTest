import { defineConfig } from 'vite'
import { resolve } from 'node:path'

export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        dashboard: resolve(import.meta.dirname, 'index.html'),
        projects: resolve(import.meta.dirname, 'projects.html'),
        inbox: resolve(import.meta.dirname, 'inbox.html'),
        analytics: resolve(import.meta.dirname, 'analytics.html'),
        settings: resolve(import.meta.dirname, 'settings.html'),
        login: resolve(import.meta.dirname, 'login.html')
      }
    }
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
