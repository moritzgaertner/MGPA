import { Badge, Box, Button, Card, Flex, Heading, HStack, IconButton, Spinner, Stack, Text } from '@chakra-ui/react'
import { useState } from 'react'
import { LuCheck, LuChevronLeft, LuChevronRight, LuDumbbell, LuSettings2 } from 'react-icons/lu'

import { addDays, type Habit, useHabitWeek, useToggleHabit } from '@/api/tracking'
import { formatDay } from '@/components/training/format'
import { toaster } from '@/components/ui/toaster'

import { ManageHabitsDialog } from './ManageHabitsDialog'

const WEEKDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']

/** This week's habits: one row of 7 day boxes per habit, progress vs. weekly goal. */
export function HabitsCard() {
  const [week, setWeek] = useState<string | undefined>(undefined) // undefined = current week
  const [managing, setManaging] = useState(false)
  const { data, isPending } = useHabitWeek(week)
  const toggle = useToggleHabit()

  const days = data ? WEEKDAYS.map((_, i) => addDays(data.week_start, i)) : []
  const isCurrentWeek = data ? data.today >= data.week_start && data.today < addDays(data.week_start, 7) : true

  const onToggle = (habit: Habit, day: string) =>
    toggle.mutate(
      { habitId: habit.id, day, done: !habit.done.includes(day), week },
      { onError: (error) => toaster.error({ title: 'Could not update the habit', description: error.message }) },
    )

  return (
    <Card.Root variant="outline">
      <Card.Body gap="4">
        <Flex justify="space-between" align="center" gap="2">
          <Heading size="md">Habits</Heading>
          <HStack gap="0">
            <IconButton
              aria-label="Previous week"
              variant="ghost"
              size="sm"
              onClick={() => data && setWeek(addDays(data.week_start, -7))}
            >
              <LuChevronLeft />
            </IconButton>
            <Text fontSize="sm" minW="24" textAlign="center">
              {data ? (isCurrentWeek ? 'This week' : `Week of ${formatDay(data.week_start)}`) : ''}
            </Text>
            <IconButton
              aria-label="Next week"
              variant="ghost"
              size="sm"
              disabled={isCurrentWeek}
              onClick={() => data && setWeek(addDays(data.week_start, 7))}
            >
              <LuChevronRight />
            </IconButton>
            <IconButton aria-label="Manage habits" variant="ghost" size="sm" onClick={() => setManaging(true)}>
              <LuSettings2 />
            </IconButton>
          </HStack>
        </Flex>

        {isPending || !data ? (
          <Spinner />
        ) : data.habits.length === 0 ? (
          <Stack align="flex-start">
            <Text color="fg.muted" fontSize="sm">
              No habits yet.
            </Text>
            <Button size="sm" variant="outline" onClick={() => setManaging(true)}>
              Add habits
            </Button>
          </Stack>
        ) : (
          <Stack gap="4">
            {data.habits.map((habit) => (
              <HabitRow
                key={habit.id}
                habit={habit}
                days={days}
                today={data.today}
                onToggle={(day) => onToggle(habit, day)}
              />
            ))}
          </Stack>
        )}
      </Card.Body>
      {managing && data && <ManageHabitsDialog habits={data.habits} onClose={() => setManaging(false)} />}
    </Card.Root>
  )
}

type HabitRowProps = { habit: Habit; days: string[]; today: string; onToggle: (day: string) => void }

function HabitRow({ habit, days, today, onToggle }: HabitRowProps) {
  const automatic = habit.source === 'training'
  const count = habit.done.length
  const reached = count >= habit.weekly_goal

  return (
    <Stack gap="1.5">
      <HStack justify="space-between">
        <HStack gap="1.5">
          {automatic && <LuDumbbell title="Counted automatically from logged workouts" />}
          <Text fontWeight="medium">{habit.name}</Text>
        </HStack>
        <Badge colorPalette={reached ? 'green' : 'gray'} variant={reached ? 'solid' : 'subtle'}>
          {count}/{habit.weekly_goal}
        </Badge>
      </HStack>
      <HStack gap="1.5">
        {days.map((day, index) => {
          const done = habit.done.includes(day)
          const future = day > today
          return (
            <Box key={day} flex="1" textAlign="center">
              <Text fontSize="2xs" color={day === today ? 'fg' : 'fg.muted'} fontWeight={day === today ? 'bold' : undefined}>
                {WEEKDAYS[index]}
              </Text>
              <IconButton
                aria-label={`${habit.name} ${day}`}
                aria-pressed={done}
                size="sm"
                w="full"
                minW="0"
                variant={done ? 'solid' : 'outline'}
                colorPalette={done ? 'teal' : 'gray'}
                disabled={automatic || future}
                onClick={() => onToggle(day)}
              >
                {done ? <LuCheck /> : null}
              </IconButton>
            </Box>
          )
        })}
      </HStack>
    </Stack>
  )
}
