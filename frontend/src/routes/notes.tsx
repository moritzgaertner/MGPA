import { Box, Button, Heading, HStack, SimpleGrid, Spinner, Stack, Text } from '@chakra-ui/react'
import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { LuPlus } from 'react-icons/lu'

import type { Note } from '@/api/client'
import { useDeleteNote, useNotes, useUpdateNote } from '@/api/notes'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { NoteCard } from '@/components/notes/NoteCard'
import { NoteEditorDialog } from '@/components/notes/NoteEditorDialog'
import { toaster } from '@/components/ui/toaster'

export const Route = createFileRoute('/notes')({
  component: NotesPage,
})

// Rough rule of thumb for English/German text: 1 token ≈ 4 characters.
const estimateTokens = (text: string) => Math.ceil(text.length / 4)

function NotesPage() {
  const { data: notes, isPending, isError } = useNotes()
  const updateNote = useUpdateNote()
  const deleteNote = useDeleteNote()

  // Which dialog is open: editing a note, creating one ('new'), or deleting one.
  const [editing, setEditing] = useState<Note | 'new' | null>(null)
  const [deleting, setDeleting] = useState<Note | null>(null)

  const togglePin = (note: Note) =>
    updateNote.mutate(
      { id: note.id, changes: { is_pinned: !note.is_pinned } },
      { onError: (error) => toaster.error({ title: 'Could not change pin', description: error.message }) },
    )

  const pinned = notes?.filter((note) => note.is_pinned) ?? []
  const others = notes?.filter((note) => !note.is_pinned) ?? []
  const pinnedTokens = pinned.reduce((sum, note) => sum + estimateTokens(note.title + note.content), 0)

  const renderCards = (list: Note[]) => (
    <SimpleGrid columns={{ base: 1, lg: 2 }} gap="3">
      {list.map((note) => (
        <NoteCard
          key={note.id}
          note={note}
          onTogglePin={() => togglePin(note)}
          onEdit={() => setEditing(note)}
          onDelete={() => setDeleting(note)}
          pinPending={updateNote.isPending && updateNote.variables?.id === note.id}
        />
      ))}
    </SimpleGrid>
  )

  return (
    <Box maxW="5xl" mx="auto" p={{ base: '4', md: '8' }}>
      <HStack justify="space-between" mb="6">
        <Heading size="2xl">Notes</Heading>
        <Button colorPalette="teal" onClick={() => setEditing('new')}>
          <LuPlus /> New note
        </Button>
      </HStack>

      {isPending && <Spinner />}
      {isError && <Text color="fg.error">Could not load notes. Is the backend running?</Text>}
      {notes?.length === 0 && (
        <Text color="fg.muted">
          No notes yet. Pin a note (e.g. your training plan) and the assistant knows it in every chat.
        </Text>
      )}

      <Stack gap="8">
        {pinned.length > 0 && (
          <Stack gap="3">
            <Box>
              <Heading size="md">Pinned</Heading>
              {/* Cost awareness: pinned notes are sent with EVERY chat message. */}
              <Text fontSize="sm" color="fg.muted">
                Sent word for word with every chat message — about {pinnedTokens.toLocaleString()} tokens each time.
              </Text>
            </Box>
            {renderCards(pinned)}
          </Stack>
        )}
        {others.length > 0 && (
          <Stack gap="3">
            {pinned.length > 0 && <Heading size="md">Other notes</Heading>}
            {renderCards(others)}
          </Stack>
        )}
      </Stack>

      {editing && (
        <NoteEditorDialog note={editing === 'new' ? undefined : editing} onClose={() => setEditing(null)} />
      )}
      {deleting && (
        <ConfirmDialog
          title="Delete note?"
          message={`“${deleting.title}” will be deleted. This cannot be undone.`}
          confirmLabel="Delete"
          loading={deleteNote.isPending}
          onClose={() => setDeleting(null)}
          onConfirm={() =>
            deleteNote.mutate(deleting.id, {
              onSuccess: () => setDeleting(null),
              onError: (error) => toaster.error({ title: 'Delete failed', description: error.message }),
            })
          }
        />
      )}
    </Box>
  )
}
