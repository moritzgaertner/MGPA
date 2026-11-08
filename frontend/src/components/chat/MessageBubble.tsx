import { Box, Flex, Spinner } from '@chakra-ui/react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { Prose } from '@/components/ui/prose'

type MessageBubbleProps = {
  role: 'user' | 'assistant'
  content: string
  /** True while this answer is still being streamed in. */
  streaming?: boolean
}

/**
 * One chat message. User messages: plain text in a bubble on the right.
 * Assistant messages: rendered Markdown (lists, code, tables) on the left.
 */
export function MessageBubble({ role, content, streaming = false }: MessageBubbleProps) {
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
      {/* react-markdown never renders raw HTML from the text, so model output can't inject
          scripts into the page (XSS). */}
      <Prose maxW="full" color="fg" fontSize="md">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </Prose>
      {streaming && <Spinner size="xs" color="fg.muted" mt="1" />}
    </Box>
  )
}
