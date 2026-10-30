import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    // Use the "@/*" path alias from tsconfig.app.json
    tsconfigPaths: true,
  },
})
