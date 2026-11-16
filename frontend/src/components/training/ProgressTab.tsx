import { Card, Heading, NativeSelect, SimpleGrid, Spinner, Stack, Stat, Text } from '@chakra-ui/react'
import { Chart, useChart } from '@chakra-ui/charts'
import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts'

import { useExerciseHistory, useMonthlySessions, useTrainingPlan } from '@/api/training'

import { formatDay } from './format'

/** Weight progression of one exercise + sessions per month. */
export function ProgressTab() {
  const { data: plans } = useTrainingPlan()
  const exercises = plans?.flatMap((plan) => plan.exercises.map((e) => ({ ...e, focus: plan.focus }))) ?? []
  const [selectedId, setSelectedId] = useState<number | undefined>(undefined)
  const exerciseId = selectedId ?? exercises[0]?.id
  const exercise = exercises.find((e) => e.id === exerciseId)

  return (
    <Stack gap="6">
      <Stack gap="3">
        <NativeSelect.Root maxW="sm">
          <NativeSelect.Field value={exerciseId ?? ''} onChange={(e) => setSelectedId(Number(e.target.value))}>
            {exercises.map((e) => (
              <option key={e.id} value={e.id}>
                {e.focus} · {e.name}
              </option>
            ))}
          </NativeSelect.Field>
          <NativeSelect.Indicator />
        </NativeSelect.Root>
        {exercise && <ExerciseProgress exerciseId={exercise.id} unit={exercise.unit} />}
      </Stack>
      <MonthlySessions />
    </Stack>
  )
}

function ExerciseProgress({ exerciseId, unit }: { exerciseId: number; unit: string }) {
  const { data: history, isPending } = useExerciseHistory(exerciseId)
  const chart = useChart({
    data: (history ?? []).map((point) => ({ day: formatDay(point.date), weight: point.weight })),
    series: [{ name: 'weight', color: 'teal.solid' }],
  })

  if (isPending) return <Spinner />
  if (!history || history.length === 0) return <Text color="fg.muted">No entries for this exercise yet.</Text>

  const first = history[0].weight
  const last = history[history.length - 1].weight
  const best = Math.max(...history.map((p) => p.weight))
  const change = first ? ((last - first) / first) * 100 : 0

  return (
    <Stack gap="4">
      <SimpleGrid columns={{ base: 3 }} gap="3">
        <Stat.Root>
          <Stat.Label>Current</Stat.Label>
          <Stat.ValueText>
            {last.toLocaleString()} {unit}
          </Stat.ValueText>
        </Stat.Root>
        <Stat.Root>
          <Stat.Label>Best</Stat.Label>
          <Stat.ValueText>
            {best.toLocaleString()} {unit}
          </Stat.ValueText>
        </Stat.Root>
        <Stat.Root>
          <Stat.Label>Since start</Stat.Label>
          <Stat.ValueText color={change >= 0 ? 'fg.success' : 'fg.error'}>
            {change >= 0 ? '+' : ''}
            {change.toFixed(1)} %
          </Stat.ValueText>
        </Stat.Root>
      </SimpleGrid>
      <Chart.Root maxH="xs" chart={chart}>
        <LineChart data={chart.data} margin={{ left: -10, right: 10 }}>
          <CartesianGrid stroke={chart.color('border')} vertical={false} />
          <XAxis dataKey={chart.key('day')} stroke={chart.color('border')} tickLine={false} />
          <YAxis stroke={chart.color('border')} tickLine={false} domain={['auto', 'auto']} />
          <Tooltip animationDuration={100} cursor={false} content={<Chart.Tooltip />} />
          {chart.series.map((item) => (
            <Line
              key={item.name}
              type="monotone"
              isAnimationActive={false}
              dataKey={chart.key(item.name)}
              stroke={chart.color(item.color)}
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          ))}
        </LineChart>
      </Chart.Root>
    </Stack>
  )
}

function MonthlySessions() {
  const { data: months } = useMonthlySessions()
  const chart = useChart({
    data: (months ?? []).map((m) => ({
      month: new Date(`${m.month}-01T00:00:00`).toLocaleDateString('de-DE', { month: 'short', year: '2-digit' }),
      sessions: m.sessions,
    })),
    series: [{ name: 'sessions', color: 'teal.solid' }],
  })

  if (!months || months.length === 0) return null
  return (
    <Card.Root variant="outline">
      <Card.Body gap="3">
        <Heading size="sm">Sessions per month</Heading>
        <Chart.Root maxH="2xs" chart={chart}>
          <BarChart data={chart.data} margin={{ left: -20 }}>
            <CartesianGrid stroke={chart.color('border')} vertical={false} />
            <XAxis dataKey={chart.key('month')} stroke={chart.color('border')} tickLine={false} />
            <YAxis stroke={chart.color('border')} tickLine={false} allowDecimals={false} />
            <Tooltip animationDuration={100} cursor={false} content={<Chart.Tooltip />} />
            {chart.series.map((item) => (
              <Bar key={item.name} isAnimationActive={false} dataKey={chart.key(item.name)} fill={chart.color(item.color)} radius={4} />
            ))}
          </BarChart>
        </Chart.Root>
      </Card.Body>
    </Card.Root>
  )
}
