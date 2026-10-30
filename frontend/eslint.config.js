// ESLint "flat config": which rules check the frontend code (the frontend's ruff).
import js from '@eslint/js'
import { defineConfig, globalIgnores } from 'eslint/config'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default defineConfig([
  // Build output and generated code are not linted. src/components/ui holds Chakra's
  // CLI-generated snippets (npx @chakra-ui/cli snippet add), vendored as-is.
  globalIgnores(['dist', 'src/api/schema.d.ts', 'src/routeTree.gen.ts', 'src/components/ui']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended, // general JavaScript mistakes
      tseslint.configs.recommended, // TypeScript-specific mistakes
      reactHooks.configs.flat['recommended-latest'], // correct use of React hooks
      reactRefresh.configs.vite, // keeps hot reload working
    ],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
  },
])
