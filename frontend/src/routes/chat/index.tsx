import { createFileRoute } from '@tanstack/react-router'

import { PagePlaceholder } from '@/components/PagePlaceholder'

// /chat — a new, empty chat. The first message creates the conversation.
export const Route = createFileRoute('/chat/')({
  component: NewChatPage,
})

function NewChatPage() {
  return (
    <PagePlaceholder
      title="What can I help with?"
      description="Sending messages arrives in step 5."
    />
  )
}
