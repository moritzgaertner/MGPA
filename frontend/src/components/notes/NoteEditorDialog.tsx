import { Button, Dialog, Field, Input, Portal, Stack, Switch, Textarea } from '@chakra-ui/react'
import { useState } from 'react'

import type { Note } from '@/api/client'
import { useCreateNote, useUpdateNote } from '@/api/notes'
import { toaster } from '@/components/ui/toaster'

// Same limits as the backend (schemas.py); the backend enforces them, the UI just helps.
const TITLE_MAX = 200
const CONTENT_MAX = 10_000

type NoteEditorDialogProps = {
  /** Existing note to edit; omitted = create a new one. */
  note?: Note
  onClose: () => void
}

export function NoteEditorDialog({ note, onClose }: NoteEditorDialogProps) {
  const [title, setTitle] = useState(note?.title ?? '')
  const [content, setContent] = useState(note?.content ?? '')
  const [pinned, setPinned] = useState(note?.is_pinned ?? false)
  const createNote = useCreateNote()
  const updateNote = useUpdateNote()

  const valid = title.trim() !== '' && content.trim() !== ''
  const saving = createNote.isPending || updateNote.isPending

  const save = () => {
    const fields = { title: title.trim(), content: content.trim(), is_pinned: pinned }
    const callbacks = {
      onSuccess: onClose,
      onError: (error: Error) => toaster.error({ title: 'Saving failed', description: error.message }),
    }
    if (note) updateNote.mutate({ id: note.id, changes: fields }, callbacks)
    else createNote.mutate(fields, callbacks)
  }

  return (
    <Dialog.Root open onOpenChange={(details) => !details.open && onClose()} placement="center" size="lg">
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content>
            <form
              onSubmit={(event) => {
                event.preventDefault()
                if (valid) save()
              }}
            >
              <Dialog.Header>
                <Dialog.Title>{note ? 'Edit note' : 'New note'}</Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                <Stack gap="4">
                  <Field.Root required>
                    <Field.Label>Title</Field.Label>
                    <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={TITLE_MAX} autoFocus />
                  </Field.Root>
                  <Field.Root required>
                    <Field.Label>Content</Field.Label>
                    <Textarea
                      value={content}
                      onChange={(e) => setContent(e.target.value)}
                      maxLength={CONTENT_MAX}
                      rows={10}
                      placeholder="Markdown works, e.g. lists or **bold**."
                    />
                    <Field.HelperText>
                      {content.length.toLocaleString()} / {CONTENT_MAX.toLocaleString()} characters
                    </Field.HelperText>
                  </Field.Root>
                  <Switch.Root checked={pinned} onCheckedChange={(details) => setPinned(details.checked)}>
                    <Switch.HiddenInput />
                    <Switch.Control />
                    <Switch.Label>Pin — include word for word in every chat</Switch.Label>
                  </Switch.Root>
                </Stack>
              </Dialog.Body>
              <Dialog.Footer>
                <Button variant="outline" onClick={onClose}>
                  Cancel
                </Button>
                <Button type="submit" colorPalette="teal" disabled={!valid} loading={saving}>
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
