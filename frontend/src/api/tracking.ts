import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from './client'
import type { components } from './schema'

export type WeightPoint = components['schemas']['WeightPoint']
export type HabitWeek = components['schemas']['HabitWeekRead']
export type Habit = components['schemas']['HabitRead']

export const trackingKeys = {
  all: ['tracking'] as const,
  weights: (days: number) => [...trackingKeys.all, 'weights', days] as const,
  weekly: (weeks: number) => [...trackingKeys.all, 'weekly', weeks] as const,
  habits: (week: string | undefined) => [...trackingKeys.all, 'habits', week ?? 'current'] as const,
}

// --- Body weight -------------------------------------------------------------------------------

export function useWeights(days: number) {
  return useQuery({
    queryKey: trackingKeys.weights(days),
    queryFn: async () => unwrap(await api.GET('/tracking/weight', { params: { query: { days } } })),
  })
}

export function useWeeklyWeights(weeks: number) {
  return useQuery({
    queryKey: trackingKeys.weekly(weeks),
    queryFn: async () => unwrap(await api.GET('/tracking/weight/weekly', { params: { query: { weeks } } })),
  })
}

export function useSaveWeight() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ day, weight }: { day: string; weight: number }) =>
      unwrap(await api.PUT('/tracking/weight/{day}', { params: { path: { day } }, body: { weight } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: trackingKeys.all }),
  })
}

export function useDeleteWeight() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (day: string) => {
      unwrap(await api.DELETE('/tracking/weight/{day}', { params: { path: { day } } }))
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: trackingKeys.all }),
  })
}

// --- Habits ------------------------------------------------------------------------------------

export function useHabitWeek(week: string | undefined) {
  return useQuery({
    queryKey: trackingKeys.habits(week),
    queryFn: async () =>
      unwrap(await api.GET('/tracking/habits', { params: { query: week ? { week } : {} } })),
  })
}

type Toggle = { habitId: number; day: string; done: boolean; week: string | undefined }

/** Tick/untick a habit. The checkbox flips immediately (optimistic); on error it flips back. */
export function useToggleHabit() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ habitId, day, done }: Toggle) => {
      const params = { params: { path: { habit_id: habitId, day } } }
      if (done) unwrap(await api.PUT('/tracking/habits/{habit_id}/checks/{day}', params))
      else unwrap(await api.DELETE('/tracking/habits/{habit_id}/checks/{day}', params))
    },
    onMutate: async ({ habitId, day, done, week }) => {
      const key = trackingKeys.habits(week)
      await queryClient.cancelQueries({ queryKey: key })
      const previous = queryClient.getQueryData<HabitWeek>(key)
      if (previous) {
        queryClient.setQueryData<HabitWeek>(key, {
          ...previous,
          habits: previous.habits.map((habit) =>
            habit.id !== habitId
              ? habit
              : { ...habit, done: done ? [...habit.done, day].sort() : habit.done.filter((d) => d !== day) },
          ),
        })
      }
      return { key, previous }
    },
    onError: (_error, _toggle, context) => {
      if (context?.previous) queryClient.setQueryData(context.key, context.previous)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: [...trackingKeys.all, 'habits'] }),
  })
}

export function useCreateHabit() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name: string; weekly_goal: number }) =>
      unwrap(await api.POST('/tracking/habits', { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: trackingKeys.all }),
  })
}

export function useUpdateHabit() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: number; weekly_goal?: number; is_active?: boolean }) => {
      unwrap(await api.PATCH('/tracking/habits/{habit_id}', { params: { path: { habit_id: id } }, body }))
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: trackingKeys.all }),
  })
}

// --- Dates (ISO strings "YYYY-MM-DD", no time zones involved) -----------------------------------

/** Today's date in the browser's time zone. */
export const isoToday = () => new Date().toLocaleDateString('sv-SE') // Swedish locale = ISO format

export function addDays(iso: string, days: number) {
  const date = new Date(`${iso}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}
