import { Box, Button, Dialog, HStack, IconButton, Input, Menu, Portal, Spinner, Stack, Text } from '@chakra-ui/react'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { useState } from 'react'
import { LuEllipsis, LuPencil, LuTrash2 } from 'react-icons/lu'

import type { Conversation } from '@/api/client'
import { useConversations, useDeleteConversation, useRenameConversation } from '@/api/conversations'
import { toaster } from '@/components/ui/toaster'

export const UNTITLED = 'New conversation'

type ConversationListProps = {
  onNavigate?: () => void
}

/** Sidebar list of all conversations, with rename/delete per item. */
export function ConversationList({ onNavigate }: ConversationListProps) {
  const { data: conversations, isPending, isError } = useConversations()
  // Which conversation a dialog is open for (null = dialog closed).
  const [renaming, setRenaming] = useState<Conversation | null>(null)
  const [deleting, setDeleting] = useState<Conversation | null>(null)

  if (isPending) return <Spinner size="sm" mx="2" />
  if (isError) {
    return (
      <Text fontSize="sm" color="fg.error" px="2">
        Could not load conversations. Is the backend running?
      </Text>
    )
  }
  if (conversations.length === 0) {
    return (
      <Text fontSize="sm" color="fg.muted" px="2">
        No conversations yet.
      </Text>
    )
  }

  return (
    <>
      <Stack gap="0.5">
        {conversations.map((conversation) => (
          <HStack key={conversation.id} gap="0">
            <Button
              asChild
              variant="ghost"
              size="sm"
              flex="1"
              minW="0"
              justifyContent="flex-start"
              fontWeight="normal"
              _currentPage={{ bg: 'bg.emphasized', fontWeight: 'medium' }}
            >
              <Link
                to="/chat/$conversationId"
                params={{ conversationId: conversation.id }}
                onClick={onNavigate}
              >
                <Text truncate>{conversation.title ?? UNTITLED}</Text>
              </Link>
            </Button>

            <Menu.Root>
              <Menu.Trigger asChild>
                <IconButton aria-label="Conversation actions" variant="ghost" size="xs">
                  <LuEllipsis />
                </IconButton>
              </Menu.Trigger>
              <Portal>
                <Menu.Positioner>
                  <Menu.Content>
                    <Menu.Item value="rename" onSelect={() => setRenaming(conversation)}>
                      <LuPencil /> Rename
                    </Menu.Item>
                    <Menu.Item
                      value="delete"
                      color="fg.error"
                      _hover={{ bg: 'bg.error', color: 'fg.error' }}
                      onSelect={() => setDeleting(conversation)}
                    >
                      <LuTrash2 /> Delete
                    </Menu.Item>
                  </Menu.Content>
                </Menu.Positioner>
              </Portal>
            </Menu.Root>
          </HStack>
        ))}
      </Stack>

      {renaming && <RenameDialog conversation={renaming} onClose={() => setRenaming(null)} />}
      {deleting && <DeleteDialog conversation={deleting} onClose={() => setDeleting(null)} />}
    </>
  )
}

type DialogProps = {
  conversation: Conversation
  onClose: () => void
}

function RenameDialog({ conversation, onClose }: DialogProps) {
  const [title, setTitle] = useState(conversation.title ?? '')
  const rename = useRenameConversation()
  const trimmed = title.trim()

  const save = () => {
    rename.mutate(
      { id: conversation.id, title: trimmed },
      {
        onSuccess: onClose,
        onError: (error) => toaster.error({ title: 'Rename failed', description: error.message }),
      },
    )
  }

  return (
    <Dialog.Root open onOpenChange={(details) => !details.open && onClose()} placement="center">
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content>
            {/* A form, so Enter in the input saves. */}
            <form
              onSubmit={(event) => {
                event.preventDefault()
                if (trimmed) save()
              }}
            >
              <Dialog.Header>
                <Dialog.Title>Rename conversation</Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                <Input
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  maxLength={200}
                  placeholder={UNTITLED}
                  autoFocus
                />
              </Dialog.Body>
              <Dialog.Footer>
                <Button variant="outline" onClick={onClose}>
                  Cancel
                </Button>
                <Button type="submit" disabled={!trimmed} loading={rename.isPending}>
                  Save
                </Button>
              </Dialog.Footer>
            </form>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  )
}

function DeleteDialog({ conversation, onClose }: DialogProps) {
  const deleteConversation = useDeleteConversation()
  const navigate = useNavigate()
  // If the conversation being deleted is the one currently open, leave its page afterwards.
  const params = useParams({ strict: false })

  const confirm = () => {
    deleteConversation.mutate(conversation.id, {
      onSuccess: () => {
        onClose()
        if (params.conversationId === conversation.id) void navigate({ to: '/chat' })
      },
      onError: (error) => toaster.error({ title: 'Delete failed', description: error.message }),
    })
  }

  return (
    <Dialog.Root open onOpenChange={(details) => !details.open && onClose()} placement="center" role="alertdialog">
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content>
            <Dialog.Header>
              <Dialog.Title>Delete conversation?</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <Box>
                <Text>
                  “{conversation.title ?? UNTITLED}” and all its messages will be deleted. This cannot be
                  undone.
                </Text>
              </Box>
            </Dialog.Body>
            <Dialog.Footer>
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button colorPalette="red" onClick={confirm} loading={deleteConversation.isPending}>
                Delete
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  )
}
