import { Box, Flex, HStack, Spinner, Stack, Text } from '@chakra-ui/react'
import { LuSearch } from 'react-icons/lu'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import type { Action } from '@/api/actions'
import { Prose } from '@/components/ui/prose'

import { ActionCard } from './ActionCard'

type MessageBubbleProps = {
  role: 'user' | 'assistant'
  content: string
  /** True while this answer is still being streamed in. */
  streaming?: boolean
  /** Tool activity shown above an answer while it streams (e.g. a knowledge-base search). */
  activities?: string[]
  /** Proposals made in this answer, shown as confirm/discard cards below it. */
  actions?: Action[]
}

/**
 * One chat message. User messages: plain text in a bubble on the right.
 * Assistant messages: rendered Markdown (lists, code, tables) on the left, plus proposal cards.
 */
export function MessageBubble({
  role,
  content,
  streaming = false,
  activities = [],
  actions = [],
}: MessageBubbleProps) {
  if (role === 'user') {
    return (
      <Flex justify="flex-end">
        <Box bg="bg.muted" px="4" py="2" rounded="2xl" maxW="85%" whiteSpace="pre-wrap">
          {content}
        </Box>
      </Flex>
    )
  }

  return (
    <Box>
      {activities.map((activity, index) => (
        <HStack key={index} gap="2" color="fg.muted" fontSize="sm" mb="2">
          <LuSearch />
          <Text>{activity}</Text>
        </HStack>
      ))}
      {/* react-markdown never renders raw HTML from the text, so model output can't inject
          scripts into the page (XSS). */}
      {content && (
        <Prose maxW="full" color="fg" fontSize="md">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </Prose>
      )}
      {actions.length > 0 && (
        <Stack gap="2" mt="3" maxW="md">
          {actions.map((action) => (
            <ActionCard key={action.id} action={action} />
          ))}
        </Stack>
      )}
      {streaming && <Spinner size="xs" color="fg.muted" mt="1" />}
    </Box>
  )
}
