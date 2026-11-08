import { Card, HStack, IconButton, Text } from '@chakra-ui/react'
import { LuPencil, LuPin, LuPinOff, LuTrash2 } from 'react-icons/lu'

import type { Note } from '@/api/client'

type NoteCardProps = {
  note: Note
  onTogglePin: () => void
  onEdit: () => void
  onDelete: () => void
  pinPending?: boolean
}

/** One note: title, a preview of the content, and pin / edit / delete buttons. */
export function NoteCard({ note, onTogglePin, onEdit, onDelete, pinPending }: NoteCardProps) {
  return (
    <Card.Root variant="outline" borderColor={note.is_pinned ? 'teal.emphasized' : undefined}>
      <Card.Body gap="2">
        <HStack justify="space-between" align="flex-start">
          <Text fontWeight="semibold">{note.title}</Text>
          <HStack gap="0" flexShrink={0}>
            <IconButton
              aria-label={note.is_pinned ? 'Unpin note' : 'Pin note'}
              variant="ghost"
              size="sm"
              colorPalette={note.is_pinned ? 'teal' : 'gray'}
              onClick={onTogglePin}
              loading={pinPending}
            >
              {note.is_pinned ? <LuPinOff /> : <LuPin />}
            </IconButton>
            <IconButton aria-label="Edit note" variant="ghost" size="sm" onClick={onEdit}>
              <LuPencil />
            </IconButton>
            <IconButton aria-label="Delete note" variant="ghost" size="sm" onClick={onDelete}>
              <LuTrash2 />
            </IconButton>
          </HStack>
        </HStack>
        <Text color="fg.muted" fontSize="sm" whiteSpace="pre-wrap" lineClamp={6}>
          {note.content}
        </Text>
      </Card.Body>
    </Card.Root>
  )
}
