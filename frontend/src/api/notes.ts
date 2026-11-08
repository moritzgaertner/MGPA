import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from './client'
import type { components } from './schema'

export type NoteCreate = components['schemas']['NoteCreate']
export type NoteUpdate = components['schemas']['NoteUpdate']

export const noteKeys = {
  all: ['notes'] as const,
  list: () => [...noteKeys.all, 'list'] as const,
}

/** All notes, pinned first, then most recently changed (order comes from the backend). */
export function useNotes() {
  return useQuery({
    queryKey: noteKeys.list(),
    queryFn: async () => unwrap(await api.GET('/notes')),
  })
}

export function useCreateNote() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: NoteCreate) => unwrap(await api.POST('/notes', { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: noteKeys.all }),
  })
}

/** Partial update: only the fields in `changes` are sent (e.g. { is_pinned: true }). */
export function useUpdateNote() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, changes }: { id: number; changes: NoteUpdate }) =>
      unwrap(await api.PATCH('/notes/{note_id}', { params: { path: { note_id: id } }, body: changes })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: noteKeys.all }),
  })
}

export function useDeleteNote() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      unwrap(await api.DELETE('/notes/{note_id}', { params: { path: { note_id: id } } }))
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: noteKeys.all }),
  })
}
