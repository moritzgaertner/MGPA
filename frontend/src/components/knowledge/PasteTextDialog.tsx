import { Button, Dialog, Field, Input, Portal, Stack, Textarea } from '@chakra-ui/react'
import { useState } from 'react'

import { useCreateTextDocument } from '@/api/documents'
import { toaster } from '@/components/ui/toaster'

type PasteTextDialogProps = {
  onClose: () => void
}

/** Add pasted text (e.g. converted from a PDF elsewhere) as a Markdown document. */
export function PasteTextDialog({ onClose }: PasteTextDialogProps) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const createDocument = useCreateTextDocument()
  const valid = title.trim() !== '' && content.trim() !== ''

  const save = () =>
    createDocument.mutate(
      { title: title.trim(), content },
      {
        onSuccess: onClose,
        onError: (error) => toaster.error({ title: 'Could not add text', description: error.message }),
      },
    )

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
                <Dialog.Title>Paste text</Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                <Stack gap="4">
                  <Field.Root required>
                    <Field.Label>Title</Field.Label>
                    <Input
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      maxLength={200}
                      placeholder="e.g. CV 2026"
                      autoFocus
                    />
                    <Field.HelperText>Becomes the file name used in citations.</Field.HelperText>
                  </Field.Root>
                  <Field.Root required>
                    <Field.Label>Text</Field.Label>
                    <Textarea
                      value={content}
                      onChange={(e) => setContent(e.target.value)}
                      rows={14}
                      placeholder="Markdown headings (# …) help the search find the right section."
                    />
                  </Field.Root>
                </Stack>
              </Dialog.Body>
              <Dialog.Footer>
                <Button variant="outline" onClick={onClose}>
                  Cancel
                </Button>
                <Button type="submit" colorPalette="teal" disabled={!valid} loading={createDocument.isPending}>
                  Add to knowledge base
                </Button>
              </Dialog.Footer>
            </form>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  )
}
