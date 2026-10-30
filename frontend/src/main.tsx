import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
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

// Cache for all data loaded from the backend (TanStack Query).
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000, // data counts as fresh for 30 s before a background refetch
      retry: 1,
    },
  },
})

// Entry point: mount the React app into <div id="root"> from index.html.
// Provider = Chakra UI theme + dark mode; QueryClientProvider = backend data cache.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <Provider>
        <RouterProvider router={router} />
      </Provider>
    </QueryClientProvider>
  </StrictMode>,
)
