import { Badge, Card, HStack, IconButton, Spinner, Stack, Text } from '@chakra-ui/react'
import { useState } from 'react'
import { LuTrash2 } from 'react-icons/lu'

import { type TrainingSession, useDeleteTrainingSession, useTrainingSessions } from '@/api/training'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { toaster } from '@/components/ui/toaster'

import { formatAmount, formatLongDay } from './format'

/** All workouts, newest first; a wrongly logged one can be deleted. */
export function SessionsTab() {
  const { data: sessions, isPending, isError } = useTrainingSessions()
  const deleteSession = useDeleteTrainingSession()
  const [deleting, setDeleting] = useState<TrainingSession | null>(null)

  if (isPending) return <Spinner />
  if (isError) return <Text color="fg.error">Could not load sessions.</Text>
  if (sessions.length === 0) return <Text color="fg.muted">No sessions yet. Log one in the chat, e.g. “BP 77, Skull 35”.</Text>

  return (
    <Stack gap="3">
      {sessions.map((session) => (
        <Card.Root key={session.id} variant="outline" size="sm">
          <Card.Body gap="2">
            <HStack justify="space-between">
              <HStack gap="2">
                <Text fontWeight="semibold">{formatLongDay(session.date)}</Text>
                <Badge>{session.focus}</Badge>
              </HStack>
              <IconButton aria-label="Delete session" size="xs" variant="ghost" onClick={() => setDeleting(session)}>
                <LuTrash2 />
              </IconButton>
            </HStack>
            <Stack gap="0.5">
              {session.entries.map((entry, index) => (
                <HStack key={index} justify="space-between" fontSize="sm">
                  <Text>{entry.exercise}</Text>
                  <Text color="fg.muted">{formatAmount(entry.weight, entry.sets, entry.unit)}</Text>
                </HStack>
              ))}
            </Stack>
            {session.notes && (
              <Text fontSize="sm" color="fg.muted" whiteSpace="pre-wrap">
                {session.notes}
              </Text>
            )}
          </Card.Body>
        </Card.Root>
      ))}
      {deleting && (
        <ConfirmDialog
          title="Delete session?"
          message={`${deleting.focus} on ${formatLongDay(deleting.date)} with ${deleting.entries.length} exercises will be deleted.`}
          confirmLabel="Delete"
          loading={deleteSession.isPending}
          onClose={() => setDeleting(null)}
          onConfirm={() =>
            deleteSession.mutate(deleting.id, {
              onSuccess: () => setDeleting(null),
              onError: (error) => toaster.error({ title: 'Delete failed', description: error.message }),
            })
          }
        />
      )}
    </Stack>
  )
}
