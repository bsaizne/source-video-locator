/// <reference types="vite/client" />
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// Renderer build only. The Electron main process is compiled separately
// (see scripts/build:electron + electron-builder config); this Vite config
// never touches the Python backend — it builds the Vue renderer.
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  base: './',
  server: {
    port: 5173,
    strictPort: false,
  },
  test: {
    // Renderer + Electron backend tests. The Electron main is compiled to
    // `out/` (CommonJS); never run those artifacts as vitest tests.
    include: ['src/**/*.{test,spec}.ts', 'electron/backend/tests/**/*.{test,spec}.ts'],
    exclude: ['out/**', 'dist/**', 'node_modules/**'],
  },
})
