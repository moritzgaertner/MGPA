import { HStack, IconButton, Textarea } from '@chakra-ui/react'
import { useState } from 'react'
import { LuArrowUp, LuSquare } from 'react-icons/lu'

type ChatComposerProps = {
  onSend: (text: string) => void
  onStop: () => void
  /** While an answer streams in, the send button turns into a stop button. */
  streaming: boolean
}

/** Message input: Enter sends, Shift+Enter adds a new line. */
export function ChatComposer({ onSend, onStop, streaming }: ChatComposerProps) {
  const [text, setText] = useState('')

  const submit = () => {
    const trimmed = text.trim()
    if (!trimmed || streaming) return
    onSend(trimmed)
    setText('')
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <HStack align="flex-end" borderWidth="1px" rounded="2xl" p="2" bg="bg">
        <Textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            // isComposing: don't send while an input method (e.g. for accents) is mid-word.
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault()
              submit()
            }
          }}
          placeholder="Message MGPA…"
          aria-label="Message"
          autoresize
          maxH="40"
          rows={1}
          border="none"
          _focusVisible={{ outline: 'none' }}
          maxLength={20_000}
        />
        {streaming ? (
          <IconButton aria-label="Stop answer" rounded="full" size="sm" onClick={onStop}>
            <LuSquare />
          </IconButton>
        ) : (
          <IconButton
            type="submit"
            aria-label="Send message"
            rounded="full"
            size="sm"
            colorPalette="teal"
            disabled={!text.trim()}
          >
            <LuArrowUp />
          </IconButton>
        )}
      </HStack>
    </form>
  )
}
