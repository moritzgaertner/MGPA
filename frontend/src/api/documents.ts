import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, ApiError, unwrap } from './client'
import type { components } from './schema'

export type KnowledgeDocument = components['schemas']['DocumentRead']

export const documentKeys = {
  all: ['documents'] as const,
  list: () => [...documentKeys.all, 'list'] as const,
}

const inProgress = (doc: KnowledgeDocument) => doc.status === 'pending' || doc.status === 'processing'

/** All documents. While any is still being ingested, refresh every 3 s to show the new status. */
export function useDocuments() {
  return useQuery({
    queryKey: documentKeys.list(),
    queryFn: async () => unwrap(await api.GET('/documents')),
    refetchInterval: (query) => (query.state.data?.some(inProgress) ? 3_000 : false),
  })
}

/** Upload a .md/.txt file. Uses fetch directly: the body is multipart form data, not JSON. */
export function useUploadDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (file: File): Promise<KnowledgeDocument> => {
      const form = new FormData()
      form.append('file', file)
      const response = await fetch('/api/documents', { method: 'POST', body: form })
      const json = await response.json().catch(() => undefined)
      if (!response.ok) throw new ApiError(response.status, json?.detail)
      return json as KnowledgeDocument
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: documentKeys.all }),
  })
}

export function useCreateTextDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: { title: string; content: string }) =>
      unwrap(await api.POST('/documents/text', { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: documentKeys.all }),
  })
}

export function useReprocessDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(await api.POST('/documents/{document_id}/reprocess', { params: { path: { document_id: id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: documentKeys.all }),
  })
}

export function useDeleteDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      unwrap(await api.DELETE('/documents/{document_id}', { params: { path: { document_id: id } } }))
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: documentKeys.all }),
  })
}
