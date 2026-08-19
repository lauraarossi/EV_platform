import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  test: {
    // jsdom rather than node: most of what is worth testing here is behaviour
    // — chrome that folds away on scroll, money that formats in the chosen
    // currency — and none of it can be reached without a document.
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
