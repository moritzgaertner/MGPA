import { Badge, Button, Card, HStack, Stack, Text } from '@chakra-ui/react'
import { LuCheck, LuX } from 'react-icons/lu'

import { type Action, useDecideAction } from '@/api/actions'
import { formatAmount, formatSettings } from '@/components/training/format'
import { toaster } from '@/components/ui/toaster'

type ActionCardProps = {
  action: Action
}

/** Short preview of what will be written, per action kind. */
function PayloadPreview({ action }: ActionCardProps) {
  const payload = action.payload
  if (action.kind === 'create_note') {
    return (
      <Text fontSize="sm" color="fg.muted" whiteSpace="pre-wrap" lineClamp={6}>
        {String(payload.content ?? '')}
      </Text>
    )
  }
  if (action.kind === 'log_training') {
    const entries = (payload.entries ?? []) as { exercise: string; weight: number; sets: number; unit: string }[]
    return (
      <Stack gap="0.5" fontSize="sm">
        {entries.map((entry, index) => (
          <HStack key={index} justify="space-between">
            <Text>{entry.exercise}</Text>
            <Text color="fg.muted">{formatAmount(entry.weight, entry.sets, entry.unit)}</Text>
          </HStack>
        ))}
        {typeof payload.notes === 'string' && payload.notes && (
          <Text color="fg.muted" mt="1">
            {payload.notes}
          </Text>
        )}
      </Stack>
    )
  }
  if (action.kind === 'update_machine_settings') {
    const before = (payload.old_settings ?? {}) as Record<string, string>
    const after = (payload.new_settings ?? {}) as Record<string, string>
    return (
      <Stack gap="0" fontSize="sm">
        <Text color="fg.muted">Before: {Object.keys(before).length ? formatSettings(before) : '—'}</Text>
        <Text>Now: {Object.keys(after).length ? formatSettings(after) : '—'}</Text>
      </Stack>
    )
  }
  return null
}

/**
 * A proposal by the assistant. Nothing is saved until the user presses "Save";
 * afterwards the card shows the outcome instead of the buttons.
 */
export function ActionCard({ action }: ActionCardProps) {
  const decide = useDecideAction()
  const busy = decide.isPending

  const onDecide = (decision: 'confirm' | 'reject') =>
    decide.mutate(
      { id: action.id, decision },
      { onError: (error) => toaster.error({ title: 'Could not update the proposal', description: error.message }) },
    )

  return (
    <Card.Root variant="outline" size="sm" borderColor={action.status === 'proposed' ? 'teal.emphasized' : undefined}>
      <Card.Body gap="2">
        <Text fontWeight="semibold">{action.label}</Text>
        <PayloadPreview action={action} />
        {action.status === 'proposed' ? (
          <HStack>
            <Button size="sm" colorPalette="teal" onClick={() => onDecide('confirm')} loading={busy && decide.variables?.decision === 'confirm'} disabled={busy}>
              <LuCheck /> Save
            </Button>
            <Button size="sm" variant="outline" onClick={() => onDecide('reject')} loading={busy && decide.variables?.decision === 'reject'} disabled={busy}>
              <LuX /> Discard
            </Button>
          </HStack>
        ) : (
          <Stack gap="0">
            <Badge alignSelf="flex-start" colorPalette={action.status === 'confirmed' ? 'green' : 'gray'}>
              {action.status === 'confirmed' ? 'Saved' : 'Discarded'}
            </Badge>
            {action.result_summary && (
              <Text fontSize="sm" color="fg.muted" mt="1">
                {action.result_summary}
              </Text>
            )}
          </Stack>
        )}
      </Card.Body>
    </Card.Root>
  )
}
