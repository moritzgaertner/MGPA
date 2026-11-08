import { createFileRoute } from '@tanstack/react-router'

import { ChatView } from '@/components/chat/ChatView'

// /chat — a new, empty chat. The first message creates the conversation.
export const Route = createFileRoute('/chat/')({
  component: () => <ChatView />,
})
