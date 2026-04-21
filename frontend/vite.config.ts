import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import type { UserConfigExport } from 'vite'
import { defineConfig } from 'vite'

const config: UserConfigExport & {
  test?: {
    environment: string
    include: string[]
    setupFiles?: string[]
    environmentMatchGlobs?: [string, string][]
  }
} = {
  plugins: [react(), tailwindcss()],
  test: {
    // Default to node for the existing API/unit tests. Component tests opt in
    // to jsdom via environmentMatchGlobs below so a single config covers both.
    environment: 'node',
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['src/test/setup.ts'],
    environmentMatchGlobs: [
      ['src/**/*.dom.test.{ts,tsx}', 'jsdom'],
      ['src/components/**/*.test.tsx', 'jsdom'],
      ['src/context/**/*.test.tsx', 'jsdom'],
      // mobileServicesMap/mapUtils.test.ts exercises sessionStorage so it
      // needs a browser-like environment too.
      ['src/components/mobileServicesMap/*.test.ts', 'jsdom'],
    ],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/v1': 'http://127.0.0.1:8000',
    },
  },
}
export default defineConfig(config as UserConfigExport)
