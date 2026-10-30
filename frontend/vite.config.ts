import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    // Must come before react(): turns the files in src/routes into src/routeTree.gen.ts
    // and loads each page's code only when that page is opened (code splitting).
    tanstackRouter({ target: 'react', autoCodeSplitting: true }),
    react(),
  ],
  resolve: {
    // Use the "@/*" path alias from tsconfig.app.json
    tsconfigPaths: true,
  },
  server: {
    // Dev only: forward /api/* to the FastAPI backend and strip the prefix
    // (/api/conversations -> http://localhost:8000/conversations). Same origin for the
    // browser, so no CORS setup is needed.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
