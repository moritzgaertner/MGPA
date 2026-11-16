import { useMutation, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from './client'
import { conversationKeys } from './conversations'
import { noteKeys } from './notes'
import type { components } from './schema'

export type Action = components['schemas']['ActionRead']

/** Confirm (execute) or reject (discard) a proposal the assistant made. */
export function useDecideAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, decision }: { id: number; decision: 'confirm' | 'reject' }) => {
      const params = { params: { path: { action_id: id } } }
      return decision === 'confirm'
        ? unwrap(await api.POST('/actions/{action_id}/confirm', params))
        : unwrap(await api.POST('/actions/{action_id}/reject', params))
    },
    onSuccess: () => {
      // The card's status lives in the conversation; a confirmed note shows up on /notes.
      void queryClient.invalidateQueries({ queryKey: conversationKeys.all })
      void queryClient.invalidateQueries({ queryKey: noteKeys.all })
    },
  })
}
