import { useMutation, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from './client'

/** Who is logged in. Fails with ApiError 401 when there is no valid session. */
export const meQuery = {
  queryKey: ['auth', 'me'] as const,
  queryFn: async () => unwrap(await api.GET('/auth/me')),
  retry: false,
  staleTime: 5 * 60_000,
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: { username: string; password: string }) => {
      unwrap(await api.POST('/auth/login', { body }))
    },
    // Drop anything cached from before the login and load "me" fresh.
    onSuccess: () => queryClient.removeQueries(),
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      unwrap(await api.POST('/auth/logout'))
    },
    onSettled: () => queryClient.clear(),
  })
}
