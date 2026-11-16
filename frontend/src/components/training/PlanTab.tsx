import { Badge, Box, Card, Heading, HStack, IconButton, Spinner, Stack, Text } from '@chakra-ui/react'
import { useState } from 'react'
import { LuPencil } from 'react-icons/lu'

import { type ExercisePlan, useTrainingPlan } from '@/api/training'

import { formatAmount, formatDay, formatSettings } from './format'
import { SettingsDialog } from './SettingsDialog'

/** The plan per focus: order, last weight × sets, machine settings, warnings. */
export function PlanTab() {
  const { data: plans, isPending, isError } = useTrainingPlan()
  const [editing, setEditing] = useState<ExercisePlan | null>(null)

  if (isPending) return <Spinner />
  if (isError) return <Text color="fg.error">Could not load the training plan.</Text>
  if (plans.length === 0) return <Text color="fg.muted">No exercises yet — import your plan first.</Text>

  return (
    <Stack gap="4">
      {plans.map((plan) => (
        <Card.Root key={plan.focus} variant="outline">
          <Card.Header pb="2">
            <HStack justify="space-between">
              <Heading size="md">{plan.focus}</Heading>
              <Text fontSize="sm" color="fg.muted">
                {plan.last_session_date ? `last: ${formatDay(plan.last_session_date)}` : 'no session yet'}
              </Text>
            </HStack>
          </Card.Header>
          <Card.Body pt="0">
            <Stack gap="0" divideY="1px">
              {plan.exercises.map((exercise, index) => (
                <HStack key={exercise.id} py="2" gap="3" align="flex-start">
                  <Text color="fg.muted" w="4" flexShrink={0}>
                    {index + 1}
                  </Text>
                  <Box flex="1" minW="0">
                    <HStack gap="2" wrap="wrap">
                      <Text fontWeight="medium">{exercise.name}</Text>
                      {exercise.skipped_last_time && <Badge size="sm">skipped last time</Badge>}
                      {exercise.caution && (
                        <Badge size="sm" colorPalette="orange">
                          ⚠️ {exercise.caution}
                        </Badge>
                      )}
                    </HStack>
                    <Text fontSize="sm" color={Object.keys(exercise.settings).length ? 'fg' : 'fg.muted'}>
                      {Object.keys(exercise.settings).length ? `⚙️ ${formatSettings(exercise.settings)}` : 'No settings'}
                    </Text>
                    {exercise.aliases.length > 0 && (
                      <Text fontSize="xs" color="fg.muted">
                        {exercise.aliases.join(', ')}
                      </Text>
                    )}
                  </Box>
                  <Stack gap="0" align="flex-end" flexShrink={0}>
                    <Text fontWeight="semibold">
                      {exercise.last ? formatAmount(exercise.last.weight, exercise.last.sets, exercise.unit) : '—'}
                    </Text>
                    {exercise.last && (
                      <Text fontSize="xs" color="fg.muted">
                        {formatDay(exercise.last.date)}
                      </Text>
                    )}
                  </Stack>
                  <IconButton
                    aria-label={`Edit settings of ${exercise.name}`}
                    size="xs"
                    variant="ghost"
                    onClick={() => setEditing(exercise)}
                  >
                    <LuPencil />
                  </IconButton>
                </HStack>
              ))}
            </Stack>
          </Card.Body>
        </Card.Root>
      ))}
      {editing && <SettingsDialog exercise={editing} onClose={() => setEditing(null)} />}
    </Stack>
  )
}
