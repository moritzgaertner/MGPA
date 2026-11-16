import { Badge, Box, Button, Card, Heading, HStack, IconButton, Spinner, Stack, Text } from '@chakra-ui/react'
import { createFileRoute } from '@tanstack/react-router'
import { useRef, useState } from 'react'
import { LuClipboardPaste, LuRefreshCw, LuTrash2, LuUpload } from 'react-icons/lu'

import {
  type KnowledgeDocument,
  useDeleteDocument,
  useDocuments,
  useReprocessDocument,
  useUploadDocument,
} from '@/api/documents'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { PasteTextDialog } from '@/components/knowledge/PasteTextDialog'
import { toaster } from '@/components/ui/toaster'

export const Route = createFileRoute('/knowledge')({
  component: KnowledgePage,
})

const STATUS: Record<KnowledgeDocument['status'], { label: string; color: string }> = {
  pending: { label: 'Waiting', color: 'gray' },
  processing: { label: 'Processing', color: 'blue' },
  ready: { label: 'Ready', color: 'green' },
  failed: { label: 'Failed', color: 'red' },
}

const formatSize = (bytes: number) => (bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`)

function KnowledgePage() {
  const { data: documents, isPending, isError } = useDocuments()
  const upload = useUploadDocument()
  const reprocess = useReprocessDocument()
  const deleteDocument = useDeleteDocument()
  const fileInput = useRef<HTMLInputElement>(null)
  const [pasting, setPasting] = useState(false)
  const [deleting, setDeleting] = useState<KnowledgeDocument | null>(null)

  const onFileChosen = (file: File | undefined) => {
    if (!file) return
    upload.mutate(file, {
      onSuccess: (doc) => toaster.success({ title: `“${doc.filename}” uploaded`, description: 'Processing starts shortly.' }),
      onError: (error) => toaster.error({ title: 'Upload failed', description: error.message }),
    })
  }

  return (
    <Box maxW="5xl" mx="auto" p={{ base: '4', md: '8' }}>
      <Stack gap="1" mb="6">
        <HStack justify="space-between" wrap="wrap" gap="3">
          <Heading size="2xl">Knowledge base</Heading>
          <HStack>
            <Button variant="outline" onClick={() => setPasting(true)}>
              <LuClipboardPaste /> Paste text
            </Button>
            <Button colorPalette="teal" onClick={() => fileInput.current?.click()} loading={upload.isPending}>
              <LuUpload /> Upload file
            </Button>
          </HStack>
        </HStack>
        <Text color="fg.muted" fontSize="sm">
          Markdown (.md) or text (.txt) files, up to 1 MB. The assistant searches them when your question needs
          them and cites the source.
        </Text>
      </Stack>

      {/* Hidden native file picker, opened by the "Upload file" button. */}
      <input
        ref={fileInput}
        type="file"
        accept=".md,.markdown,.txt,text/markdown,text/plain"
        hidden
        onChange={(event) => {
          onFileChosen(event.target.files?.[0])
          event.target.value = '' // allow choosing the same file again
        }}
      />

      {isPending && <Spinner />}
      {isError && <Text color="fg.error">Could not load documents. Is the backend running?</Text>}
      {documents?.length === 0 && <Text color="fg.muted">No documents yet.</Text>}

      <Stack gap="3">
        {documents?.map((doc) => {
          const status = STATUS[doc.status]
          return (
            <Card.Root key={doc.id} variant="outline">
              <Card.Body gap="1">
                <HStack justify="space-between" align="flex-start">
                  <Stack gap="1" minW="0">
                    <HStack gap="2" wrap="wrap">
                      <Text fontWeight="semibold" truncate>
                        {doc.filename}
                      </Text>
                      <Badge colorPalette={status.color}>
                        {doc.status === 'processing' && <Spinner size="xs" />}
                        {status.label}
                      </Badge>
                    </HStack>
                    <Text fontSize="sm" color="fg.muted">
                      {formatSize(doc.size_bytes)}
                      {doc.chunk_count !== null && ` · ${doc.chunk_count} sections`} · added{' '}
                      {new Date(doc.created_at).toLocaleDateString()}
                    </Text>
                    {doc.error && (
                      <Text fontSize="sm" color="fg.error">
                        {doc.error}
                      </Text>
                    )}
                  </Stack>
                  <HStack gap="0" flexShrink={0}>
                    {doc.status === 'failed' && (
                      <IconButton
                        aria-label="Process again"
                        variant="ghost"
                        size="sm"
                        loading={reprocess.isPending && reprocess.variables === doc.id}
                        onClick={() => reprocess.mutate(doc.id)}
                      >
                        <LuRefreshCw />
                      </IconButton>
                    )}
                    <IconButton aria-label="Delete document" variant="ghost" size="sm" onClick={() => setDeleting(doc)}>
                      <LuTrash2 />
                    </IconButton>
                  </HStack>
                </HStack>
              </Card.Body>
            </Card.Root>
          )
        })}
      </Stack>

      {pasting && <PasteTextDialog onClose={() => setPasting(false)} />}
      {deleting && (
        <ConfirmDialog
          title="Delete document?"
          message={`“${deleting.filename}” will be removed from the knowledge base. This cannot be undone.`}
          confirmLabel="Delete"
          loading={deleteDocument.isPending}
          onClose={() => setDeleting(null)}
          onConfirm={() =>
            deleteDocument.mutate(deleting.id, {
              onSuccess: () => setDeleting(null),
              onError: (error) => toaster.error({ title: 'Delete failed', description: error.message }),
            })
          }
        />
      )}
    </Box>
  )
}
