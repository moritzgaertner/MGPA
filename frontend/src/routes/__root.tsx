import { createRootRoute, Outlet } from '@tanstack/react-router'

import { AppShell } from '@/components/layout/AppShell'
import { PagePlaceholder } from '@/components/PagePlaceholder'

// The root route wraps every page: sidebar + content area. <Outlet /> is where the
// matched child page (e.g. /notes) is rendered.
export const Route = createRootRoute({
  component: () => (
    <AppShell>
      <Outlet />
    </AppShell>
  ),
  notFoundComponent: () => (
    <PagePlaceholder title="Page not found" description="This address does not exist." />
  ),
})
