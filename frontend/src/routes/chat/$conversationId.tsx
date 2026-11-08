import { createFileRoute, notFound } from '@tanstack/react-router'

import { ChatView } from '@/components/chat/ChatView'

// /chat/42 — an existing conversation. "$conversationId" in the file name is the URL parameter.
export const Route = createFileRoute('/chat/$conversationId')({
  // The URL is text; turn it into a number once, here. Anything else is "not found".
  params: {
    parse: ({ conversationId }) => {
      const id = Number(conversationId)
      if (!Number.isInteger(id) || id < 1) throw notFound()
      return { conversationId: id }
    },
    stringify: ({ conversationId }) => ({ conversationId: String(conversationId) }),
  },
  component: ConversationPage,
})

function ConversationPage() {
  const { conversationId } = Route.useParams()
  // key: switching to another conversation starts a fresh view (no leftover state).
  return <ChatView key={conversationId} conversationId={conversationId} />
}
