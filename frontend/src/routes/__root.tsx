import type { QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext, Outlet, redirect, useRouterState } from '@tanstack/react-router'

import { meQuery } from '@/api/auth'
import { ApiError } from '@/api/client'
import { AppShell } from '@/components/layout/AppShell'
import { PagePlaceholder } from '@/components/PagePlaceholder'
import { Toaster } from '@/components/ui/toaster'

type RouterContext = { queryClient: QueryClient }

// The root route wraps every page: sidebar + content area. <Outlet /> is where the
// matched child page (e.g. /notes) is rendered. <Toaster /> shows pop-up messages.
export const Route = createRootRouteWithContext<RouterContext>()({
  // Runs before any page renders: without a valid session, go to the login page first.
  beforeLoad: async ({ context, location }) => {
    if (location.pathname === '/login') return
    try {
      await context.queryClient.ensureQueryData(meQuery)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        throw redirect({ to: '/login', search: { redirect: location.href } })
      }
      throw error
    }
  },
  component: RootLayout,
  notFoundComponent: () => (
    <PagePlaceholder title="Page not found" description="This address does not exist." />
  ),
})

function RootLayout() {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  return (
    <>
      {/* The login page is shown on its own, without the sidebar. */}
      {pathname === '/login' ? (
        <Outlet />
      ) : (
        <AppShell>
          <Outlet />
        </AppShell>
      )}
      <Toaster />
    </>
  )
}
