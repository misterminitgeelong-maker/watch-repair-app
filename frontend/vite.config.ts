import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import type { UserConfigExport } from 'vite'
import { defineConfig } from 'vite'

const appBuildId =
  process.env.VITE_APP_BUILD_ID?.trim() ||
  process.env.RAILWAY_GIT_COMMIT_SHA?.trim() ||
  'dev'

const config: UserConfigExport & { test?: { environment: string; include: string[]; setupFiles?: string[] } } = {
  plugins: [
    react(),
    tailwindcss(),
    {
      name: 'inject-app-build-id',
      transformIndexHtml(html: string) {
        return html.replace(
          /(<meta\s+name="app-build"\s+content=")[^"]*("\s*\/?>)/i,
          `$1${appBuildId}$2`,
        )
      },
    },
  ],
  define: {
    'import.meta.env.VITE_APP_BUILD_ID': JSON.stringify(appBuildId),
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['src/test/setup.ts'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      // Override when the API is on another port (e.g. a second checkout's backend).
      '/v1': process.env.VITE_DEV_API_TARGET?.trim() || 'http://127.0.0.1:8000',
    },
  },
}
export default defineConfig(config as UserConfigExport)
