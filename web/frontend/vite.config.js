import { defineConfig } from 'vite'
import { resolve } from 'node:path'
import { WEB_BRAND_NAME, WEB_BRAND_TOKEN } from './src/brand.js'

export default defineConfig({
  plugins: [{
    name: 'smarttest-web-brand',
    transformIndexHtml: html => html.replaceAll(WEB_BRAND_TOKEN, WEB_BRAND_NAME)
  }],
  build: {
    rollupOptions: {
      input: {
        dashboard: resolve(import.meta.dirname, 'index.html'),
        projects: resolve(import.meta.dirname, 'projects.html'),
        inbox: resolve(import.meta.dirname, 'inbox.html'),
        analytics: resolve(import.meta.dirname, 'analytics.html'),
        settings: resolve(import.meta.dirname, 'settings.html'),
        jira: resolve(import.meta.dirname, 'jira.html'),
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
