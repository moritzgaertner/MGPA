import { createFileRoute } from '@tanstack/react-router'

import { PagePlaceholder } from '@/components/PagePlaceholder'

export const Route = createFileRoute('/notes')({
  component: () => (
    <PagePlaceholder
      title="Notes"
      description="Create, edit and pin notes here — arrives in step 6. Pinned notes are part of every chat."
    />
  ),
})
