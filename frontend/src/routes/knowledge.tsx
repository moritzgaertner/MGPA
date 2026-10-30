import { createFileRoute } from '@tanstack/react-router'

import { PagePlaceholder } from '@/components/PagePlaceholder'

export const Route = createFileRoute('/knowledge')({
  component: () => (
    <PagePlaceholder
      title="Knowledge base"
      description="Upload PDFs and Markdown files and ask questions about them — arrives in M4."
    />
  ),
})
