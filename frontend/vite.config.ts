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
})
