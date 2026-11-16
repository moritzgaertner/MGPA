import { Badge, Box, Button, Card, Dialog, Heading, HStack, IconButton, Input, Portal, Spinner, Stack, Text } from '@chakra-ui/react'
import { useState } from 'react'
import { LuPencil } from 'react-icons/lu'

import { type ExercisePlan, useTrainingPlan, useUpdateExercise } from '@/api/training'
import { toaster } from '@/components/ui/toaster'

import { formatAmount, formatDay } from './format'

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
                    <Text fontSize="sm" color="fg.muted">
                      {exercise.gear_setting ? `Setting: ${exercise.gear_setting}` : 'No setting'}
                      {exercise.aliases.length > 0 && ` · ${exercise.aliases.join(', ')}`}
                    </Text>
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
                  <IconButton aria-label={`Edit setting of ${exercise.name}`} size="xs" variant="ghost" onClick={() => setEditing(exercise)}>
                    <LuPencil />
                  </IconButton>
                </HStack>
              ))}
            </Stack>
          </Card.Body>
        </Card.Root>
      ))}
      {editing && <GearSettingDialog exercise={editing} onClose={() => setEditing(null)} />}
    </Stack>
  )
}

function GearSettingDialog({ exercise, onClose }: { exercise: ExercisePlan; onClose: () => void }) {
  const [value, setValue] = useState(exercise.gear_setting ?? '')
  const update = useUpdateExercise()

  const save = () =>
    update.mutate(
      { id: exercise.id, gear_setting: value },
      {
        onSuccess: onClose,
        onError: (error) => toaster.error({ title: 'Could not save the setting', description: error.message }),
      },
    )

  return (
    <Dialog.Root open onOpenChange={(details) => !details.open && onClose()} placement="center">
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content>
            <form
              onSubmit={(event) => {
                event.preventDefault()
                save()
              }}
            >
              <Dialog.Header>
                <Dialog.Title>Setting · {exercise.name}</Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                <Input value={value} onChange={(e) => setValue(e.target.value)} placeholder="e.g. Stufe 6" maxLength={500} autoFocus />
              </Dialog.Body>
              <Dialog.Footer>
                <Button variant="outline" onClick={onClose}>
                  Cancel
                </Button>
                <Button type="submit" colorPalette="teal" loading={update.isPending}>
                  Save
                </Button>
              </Dialog.Footer>
            </form>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  )
}
