# mgpa-frontend

React + TypeScript single-page app for MGPA, built with Vite.

```bash
npm install          # install dependencies (exact versions from package-lock.json: npm ci)
npm run dev          # dev server on http://localhost:5173 (hot reload)
npm run lint         # ESLint
npm run typecheck    # TypeScript compiler, no output files
npm run build        # production build into dist/
npm run api:types    # regenerate src/api/schema.d.ts after backend endpoints changed
```

In development, requests to `/api/*` are forwarded to the backend on port 8000
(see `vite.config.ts`), so the backend must be running too:

```bash
cd ../backend && uv run fastapi dev src/mgpa_backend/main.py   # terminal 1
cd ../frontend && npm run dev                                  # terminal 2
```

Requires Node 24 (installed via nvm in WSL).
