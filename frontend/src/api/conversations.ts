import { skipToken, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from './client'

/**
 * Query keys: TanStack Query's names for cached data. Everything under ['conversations']
 * can be refreshed at once with invalidateQueries({ queryKey: conversationKeys.all }).
 */
export const conversationKeys = {
  all: ['conversations'] as const,
  list: () => [...conversationKeys.all, 'list'] as const,
  detail: (id: number) => [...conversationKeys.all, 'detail', id] as const,
}

/** All conversations, most recently active first (sidebar). */
export function useConversations() {
  return useQuery({
    queryKey: conversationKeys.list(),
    queryFn: async () => unwrap(await api.GET('/conversations', { params: { query: { limit: 100 } } })),
  })
}

/** Query definition for one conversation with all its messages (reused for prefetching). */
export function conversationQuery(conversationId: number) {
  return {
    queryKey: conversationKeys.detail(conversationId),
    queryFn: async () =>
      unwrap(
        await api.GET('/conversations/{conversation_id}', {
          params: { path: { conversation_id: conversationId } },
        }),
      ),
  }
}

/** One conversation with its messages. Without an id (new chat) nothing is fetched. */
export function useConversation(conversationId: number | undefined) {
  return useQuery(
    conversationId === undefined
      ? { queryKey: conversationKeys.detail(0), queryFn: skipToken }
      : conversationQuery(conversationId),
  )
}

export function useRenameConversation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, title }: { id: number; title: string }) =>
      unwrap(
        await api.PATCH('/conversations/{conversation_id}', {
          params: { path: { conversation_id: id } },
          body: { title },
        }),
      ),
    // After any change, mark cached conversation data as stale so it is fetched again.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: conversationKeys.all }),
  })
}

export function useDeleteConversation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      unwrap(
        await api.DELETE('/conversations/{conversation_id}', {
          params: { path: { conversation_id: id } },
        }),
      )
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: conversationKeys.all }),
  })
}
