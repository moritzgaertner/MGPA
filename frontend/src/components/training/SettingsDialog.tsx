import { Button, Dialog, HStack, IconButton, Input, Portal, Stack, Text } from '@chakra-ui/react'
import { useState } from 'react'
import { LuPlus, LuX } from 'react-icons/lu'

import { type ExercisePlan, useUpdateExercise } from '@/api/training'
import { toaster } from '@/components/ui/toaster'

type Row = { name: string; value: string }

/** Edit all named settings of a machine, e.g. Sitz 4 · Knie 3 · Fuß 2. */
export function SettingsDialog({ exercise, onClose }: { exercise: ExercisePlan; onClose: () => void }) {
  const initial = Object.entries(exercise.settings).map(([name, value]) => ({ name, value }))
  const [rows, setRows] = useState<Row[]>(initial.length ? initial : [{ name: '', value: '' }])
  const update = useUpdateExercise()

  const setRow = (index: number, change: Partial<Row>) =>
    setRows((current) => current.map((row, i) => (i === index ? { ...row, ...change } : row)))

  const save = () => {
    // A lone value without a name becomes the generic "Einstellung".
    const settings = Object.fromEntries(
      rows
        .filter((row) => row.value.trim())
        .map((row) => [row.name.trim() || 'Einstellung', row.value.trim()]),
    )
    update.mutate(
      { id: exercise.id, settings },
      {
        onSuccess: onClose,
        onError: (error) => toaster.error({ title: 'Could not save the settings', description: error.message }),
      },
    )
  }

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
                <Dialog.Title>Settings · {exercise.name}</Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                <Stack gap="2">
                  <Text fontSize="sm" color="fg.muted">
                    One row per adjustment, e.g. “Sitz” = “4”. Empty rows are ignored.
                  </Text>
                  {rows.map((row, index) => (
                    <HStack key={index}>
                      <Input
                        placeholder="Name (e.g. Sitz)"
                        value={row.name}
                        onChange={(e) => setRow(index, { name: e.target.value })}
                        maxLength={50}
                        autoFocus={index === 0}
                      />
                      <Input
                        placeholder="Value (e.g. 4)"
                        value={row.value}
                        onChange={(e) => setRow(index, { value: e.target.value })}
                        maxLength={100}
                      />
                      <IconButton
                        aria-label="Remove setting"
                        variant="ghost"
                        size="sm"
                        onClick={() => setRows((current) => current.filter((_, i) => i !== index))}
                      >
                        <LuX />
                      </IconButton>
                    </HStack>
                  ))}
                  <Button
                    variant="ghost"
                    size="sm"
                    alignSelf="flex-start"
                    onClick={() => setRows((current) => [...current, { name: '', value: '' }])}
                  >
                    <LuPlus /> Add setting
                  </Button>
                </Stack>
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
