import { createFileRoute } from '@tanstack/react-router'

import { PagePlaceholder } from '@/components/PagePlaceholder'

export const Route = createFileRoute('/tasks')({
  component: () => (
    <PagePlaceholder
      title="Tasks"
      description="Your to-dos, created by you or proposed by the assistant — arrives in M5."
    />
  ),
})
