import { createRouter, RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { Provider } from '@/components/ui/provider'
import { routeTree } from '@/routeTree.gen'

// The router knows every page, generated from the files in src/routes.
const router = createRouter({ routeTree })

// Tells TypeScript about our routes, so <Link to="/notez"> is a type error.
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

// Entry point: mount the React app into <div id="root"> from index.html.
// Provider = Chakra UI theme + dark mode for everything inside it.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Provider>
      <RouterProvider router={router} />
    </Provider>
  </StrictMode>,
)
