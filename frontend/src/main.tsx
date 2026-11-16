import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createRouter, RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { ApiError } from '@/api/client'
import { Provider } from '@/components/ui/provider'
import { routeTree } from '@/routeTree.gen'

/** Session expired or logged out elsewhere: any 401 sends the user to the login page. */
function redirectToLoginOn401(error: Error) {
  if (error instanceof ApiError && error.status === 401 && window.location.pathname !== '/login') {
    const redirect = window.location.pathname + window.location.search
    void router.navigate({ to: '/login', search: { redirect } })
  }
}

// Cache for all data loaded from the backend (TanStack Query).
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000, // data counts as fresh for 30 s before a background refetch
      retry: (failureCount, error) => !(error instanceof ApiError && error.status === 401) && failureCount < 1,
    },
  },
  queryCache: new QueryCache({ onError: redirectToLoginOn401 }),
  mutationCache: new MutationCache({ onError: redirectToLoginOn401 }),
})

// The router knows every page (generated from src/routes) and gets the query cache as
// context, so the root route can check the login before rendering anything.
const router = createRouter({ routeTree, context: { queryClient } })

// Tells TypeScript about our routes, so <Link to="/notez"> is a type error.
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

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
