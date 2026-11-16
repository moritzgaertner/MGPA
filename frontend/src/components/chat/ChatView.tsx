import { Box, Center, Flex, Heading, Spinner, Stack, Text } from '@chakra-ui/react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'

import type { Action } from '@/api/actions'
import { streamChat } from '@/api/chat'
import { ApiError } from '@/api/client'
import { conversationKeys, conversationQuery, useConversation } from '@/api/conversations'
import { toaster } from '@/components/ui/toaster'

import { ChatComposer } from './ChatComposer'
import { MessageBubble } from './MessageBubble'

/** The turn currently in flight: shown locally until the stored conversation is reloaded. */
type PendingTurn = {
  userText: string
  answer: string
  /** True until the stream has ended (finished, failed or stopped). */
  streaming: boolean
  /** What the assistant did along the way, e.g. "Searched knowledge base: “leg press”". */
  activities: string[]
  /** Proposals made in this answer (confirmable once the answer is stored). */
  proposals: Action[]
}

/** Human-readable label for a tool call shown above the answer (null = don't show). */
function describeTool(name: string, args: Record<string, unknown>): string | null {
  if (name === 'search_knowledge') return `Searched knowledge base: “${String(args.query ?? '')}”`
  if (name === 'find_notes') return `Looked through notes${args.query ? `: “${String(args.query)}”` : ''}`
  if (name.startsWith('propose_')) return null // shown as a proposal card instead
  return `Used tool: ${name}`
}

type ChatViewProps = {
  /** Missing on /chat: the first message creates a new conversation. */
  conversationId?: number
}

export function ChatView({ conversationId }: ChatViewProps) {
  const conversation = useConversation(conversationId)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const [pending, setPending] = useState<PendingTurn | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const messages = conversation.data?.messages ?? []

  // Keep the newest text in view while messages arrive.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [messages.length, pending?.answer])

  // Leaving the page cancels a running answer (the server then stops calling Claude).
  useEffect(() => () => abortRef.current?.abort(), [])

  const send = async (text: string) => {
    const controller = new AbortController()
    abortRef.current = controller
    setPending({ userText: text, answer: '', streaming: true, activities: [], proposals: [] })
    let id = conversationId

    try {
      for await (const event of streamChat({ conversation_id: id ?? null, message: text }, controller.signal)) {
        if (event.event === 'start') {
          id = event.data.conversation_id
          // The conversation (and the user message) are already saved: show it in the sidebar now.
          void queryClient.invalidateQueries({ queryKey: conversationKeys.list() })
        } else if (event.event === 'delta') {
          const piece = event.data.text
          setPending((turn) => turn && { ...turn, answer: turn.answer + piece })
        } else if (event.event === 'tool') {
          const activity = describeTool(event.data.name, event.data.args)
          if (activity) setPending((turn) => turn && { ...turn, activities: [...turn.activities, activity] })
        } else if (event.event === 'proposal') {
          const proposal = event.data.action
          setPending((turn) => turn && { ...turn, proposals: [...turn.proposals, proposal] })
        } else if (event.event === 'error') {
          toaster.error({ title: 'No answer', description: event.data.detail })
        }
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        const description = error instanceof ApiError ? error.message : 'Connection to the backend failed.'
        toaster.error({ title: 'Message not sent', description })
      }
    } finally {
      abortRef.current = null
      setPending((turn) => turn && { ...turn, streaming: false })
    }

    // Hand over from the local preview to the stored conversation, without a flicker:
    // first load the saved messages, then drop the preview.
    if (id !== undefined) {
      void queryClient.invalidateQueries({ queryKey: conversationKeys.list() })
      if (conversationId === undefined) {
        await queryClient.fetchQuery(conversationQuery(id))
        await navigate({ to: '/chat/$conversationId', params: { conversationId: id }, replace: true })
        return
      }
      await queryClient.invalidateQueries({ queryKey: conversationKeys.detail(id) })
    }
    setPending(null)
  }

  if (conversation.isError) {
    return (
      <Center h="full">
        <Text color="fg.muted">This conversation could not be loaded.</Text>
      </Center>
    )
  }

  const isEmpty = messages.length === 0 && !pending

  return (
    <Flex direction="column" h="full">
      <Box flex="1" overflowY="auto" px="4">
        <Stack maxW="3xl" mx="auto" py="6" gap="6">
          {conversation.isLoading && <Spinner mx="auto" />}
          {isEmpty && !conversation.isLoading && (
            <Center minH="40vh">
              <Heading size="2xl">What can I help with?</Heading>
            </Center>
          )}
          {messages.map((message) => (
            <MessageBubble key={message.id} role={message.role} content={message.content} actions={message.actions} />
          ))}
          {pending && (
            <>
              <MessageBubble role="user" content={pending.userText} />
              <MessageBubble
                role="assistant"
                content={pending.answer}
                streaming={pending.streaming}
                activities={pending.activities}
                actions={pending.proposals}
              />
            </>
          )}
          <div ref={bottomRef} />
        </Stack>
      </Box>

      <Box px="4" pb="4">
        <Box maxW="3xl" mx="auto">
          <ChatComposer
            onSend={(text) => void send(text)}
            onStop={() => abortRef.current?.abort()}
            streaming={pending !== null}
          />
        </Box>
      </Box>
    </Flex>
  )
}
