import { skipToken, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from './client'
import type { components } from './schema'

export type FocusPlan = components['schemas']['FocusPlanRead']
export type ExercisePlan = components['schemas']['ExercisePlanRead']
export type TrainingSession = components['schemas']['SessionRead']

export const trainingKeys = {
  all: ['training'] as const,
  plan: () => [...trainingKeys.all, 'plan'] as const,
  sessions: () => [...trainingKeys.all, 'sessions'] as const,
  history: (exerciseId: number) => [...trainingKeys.all, 'history', exerciseId] as const,
  monthly: () => [...trainingKeys.all, 'monthly'] as const,
}

export function useTrainingPlan() {
  return useQuery({
    queryKey: trainingKeys.plan(),
    queryFn: async () => unwrap(await api.GET('/training/plan')),
  })
}

export function useTrainingSessions() {
  return useQuery({
    queryKey: trainingKeys.sessions(),
    queryFn: async () => unwrap(await api.GET('/training/sessions', { params: { query: { limit: 100 } } })),
  })
}

export function useExerciseHistory(exerciseId: number | undefined) {
  return useQuery({
    queryKey: trainingKeys.history(exerciseId ?? 0),
    queryFn:
      exerciseId === undefined
        ? skipToken
        : async () =>
            unwrap(
              await api.GET('/training/exercises/{exercise_id}/history', {
                params: { path: { exercise_id: exerciseId } },
              }),
            ),
  })
}

export function useMonthlySessions() {
  return useQuery({
    queryKey: trainingKeys.monthly(),
    queryFn: async () => unwrap(await api.GET('/training/stats/monthly')),
  })
}

export function useDeleteTrainingSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      unwrap(await api.DELETE('/training/sessions/{session_id}', { params: { path: { session_id: id } } }))
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: trainingKeys.all }),
  })
}

export function useUpdateExercise() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, settings }: { id: number; settings: Record<string, string> }) =>
      unwrap(
        await api.PATCH('/training/exercises/{exercise_id}', {
          params: { path: { exercise_id: id } },
          body: { settings },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: trainingKeys.plan() }),
  })
}
