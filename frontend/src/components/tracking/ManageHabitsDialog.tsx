import { Button, Dialog, HStack, IconButton, Input, NativeSelect, Portal, Stack, Text } from '@chakra-ui/react'
import { useState } from 'react'
import { LuPlus, LuTrash2 } from 'react-icons/lu'

import { type Habit, useCreateHabit, useUpdateHabit } from '@/api/tracking'
import { toaster } from '@/components/ui/toaster'

const GOALS = [1, 2, 3, 4, 5, 6, 7]

function GoalSelect({ value, onChange, label }: { value: number; onChange: (goal: number) => void; label: string }) {
  return (
    <NativeSelect.Root size="sm" width="28">
      <NativeSelect.Field aria-label={label} value={value} onChange={(e) => onChange(Number(e.target.value))}>
        {GOALS.map((goal) => (
          <option key={goal} value={goal}>
            {goal}× / week
          </option>
        ))}
      </NativeSelect.Field>
      <NativeSelect.Indicator />
    </NativeSelect.Root>
  )
}

/** Add habits, change weekly goals, remove habits (their history is kept). Changes save at once. */
export function ManageHabitsDialog({ habits, onClose }: { habits: Habit[]; onClose: () => void }) {
  const create = useCreateHabit()
  const update = useUpdateHabit()
  const [name, setName] = useState('')
  const [goal, setGoal] = useState(7)

  const onError = (error: Error) => toaster.error({ title: 'Could not save', description: error.message })

  return (
    <Dialog.Root open onOpenChange={(details) => !details.open && onClose()} placement="center">
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content>
            <Dialog.Header>
              <Dialog.Title>Manage habits</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <Stack gap="3">
                {habits.map((habit) => (
                  <HStack key={habit.id} justify="space-between">
                    <Text flex="1">{habit.name}</Text>
                    <GoalSelect
                      label={`Weekly goal for ${habit.name}`}
                      value={habit.weekly_goal}
                      onChange={(weekly_goal) => update.mutate({ id: habit.id, weekly_goal }, { onError })}
                    />
                    <IconButton
                      aria-label={`Remove ${habit.name}`}
                      variant="ghost"
                      size="sm"
                      onClick={() => update.mutate({ id: habit.id, is_active: false }, { onError })}
                    >
                      <LuTrash2 />
                    </IconButton>
                  </HStack>
                ))}
                <form
                  onSubmit={(event) => {
                    event.preventDefault()
                    if (!name.trim()) return
                    create.mutate(
                      { name: name.trim(), weekly_goal: goal },
                      { onSuccess: () => setName(''), onError },
                    )
                  }}
                >
                  <HStack pt="2" borderTopWidth="1px">
                    <Input
                      size="sm"
                      placeholder="New habit, e.g. Meditation"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      maxLength={100}
                    />
                    <GoalSelect label="Weekly goal for the new habit" value={goal} onChange={setGoal} />
                    <IconButton
                      type="submit"
                      aria-label="Add habit"
                      size="sm"
                      colorPalette="teal"
                      disabled={!name.trim()}
                      loading={create.isPending}
                    >
                      <LuPlus />
                    </IconButton>
                  </HStack>
                </form>
                <Text fontSize="xs" color="fg.muted">
                  Removed habits disappear from the list; their history is kept.
                </Text>
              </Stack>
            </Dialog.Body>
            <Dialog.Footer>
              <Button variant="outline" onClick={onClose}>
                Done
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  )
}
