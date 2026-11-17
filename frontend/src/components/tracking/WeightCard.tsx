import { Button, Card, Heading, HStack, Input, SimpleGrid, Spinner, Stack, Stat, Table, Text } from '@chakra-ui/react'
import { Chart, useChart } from '@chakra-ui/charts'
import { useState } from 'react'
import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts'

import { addDays, isoToday, useSaveWeight, useWeeklyWeights, useWeights, type WeightPoint } from '@/api/tracking'
import { formatDay } from '@/components/training/format'
import { toaster } from '@/components/ui/toaster'

const kg = (value: number) => `${value.toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} kg`

const average = (points: WeightPoint[]) =>
  points.length ? points.reduce((sum, p) => sum + p.weight, 0) / points.length : undefined

/** Weigh-in field, trend numbers, chart and weekly averages. */
export function WeightCard() {
  const { data: weights, isPending } = useWeights(90)
  const { data: weekly } = useWeeklyWeights(8)
  const today = isoToday()
  const todays = weights?.find((p) => p.date === today)

  const sevenDaysAgo = addDays(today, -7)
  const fourteenDaysAgo = addDays(today, -14)
  const thisWeek = average((weights ?? []).filter((p) => p.date > sevenDaysAgo))
  const lastWeek = average((weights ?? []).filter((p) => p.date > fourteenDaysAgo && p.date <= sevenDaysAgo))
  const latest = weights?.at(-1)

  return (
    <Card.Root variant="outline">
      <Card.Body gap="4">
        <Heading size="md">Body weight</Heading>
        <WeighIn today={today} current={todays?.weight} />

        {isPending ? (
          <Spinner />
        ) : !weights || weights.length === 0 ? (
          <Text color="fg.muted" fontSize="sm">
            No weigh-ins yet. Tip: weigh yourself every morning before breakfast — the weekly average shows the real
            trend.
          </Text>
        ) : (
          <>
            <SimpleGrid columns={3} gap="3">
              <Stat.Root>
                <Stat.Label>Latest</Stat.Label>
                <Stat.ValueText fontSize="lg">{latest ? kg(latest.weight) : '—'}</Stat.ValueText>
                {latest && <Stat.HelpText>{formatDay(latest.date)}</Stat.HelpText>}
              </Stat.Root>
              <Stat.Root>
                <Stat.Label>Ø 7 days</Stat.Label>
                <Stat.ValueText fontSize="lg">{thisWeek !== undefined ? kg(thisWeek) : '—'}</Stat.ValueText>
              </Stat.Root>
              <Stat.Root>
                <Stat.Label>vs. week before</Stat.Label>
                <Stat.ValueText fontSize="lg">
                  {thisWeek !== undefined && lastWeek !== undefined
                    ? `${thisWeek - lastWeek >= 0 ? '+' : ''}${(thisWeek - lastWeek).toFixed(1)} kg`
                    : '—'}
                </Stat.ValueText>
              </Stat.Root>
            </SimpleGrid>
            <WeightChart weights={weights} />
          </>
        )}

        {weekly && weekly.length > 0 && (
          <Table.Root size="sm">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Week of</Table.ColumnHeader>
                <Table.ColumnHeader textAlign="end">Ø weight</Table.ColumnHeader>
                <Table.ColumnHeader textAlign="end">Weigh-ins</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {[...weekly].reverse().map((week) => (
                <Table.Row key={week.week_start}>
                  <Table.Cell>{formatDay(week.week_start)}</Table.Cell>
                  <Table.Cell textAlign="end">{kg(week.average)}</Table.Cell>
                  <Table.Cell textAlign="end">{week.entries}</Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        )}
      </Card.Body>
    </Card.Root>
  )
}

function WeighIn({ today, current }: { today: string; current: number | undefined }) {
  // Starts empty; today's saved value is shown as the placeholder. (Not remounting this
  // component on new data matters: mutate() callbacks don't fire after an unmount.)
  const [value, setValue] = useState('')
  const save = useSaveWeight()
  // Accept "82,4" (German keyboard) as well as "82.4".
  const parsed = Number(value.replace(',', '.'))
  const valid = value.trim() !== '' && Number.isFinite(parsed) && parsed >= 20 && parsed <= 400

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        if (!valid) return
        save.mutate(
          { day: today, weight: parsed },
          {
            onSuccess: () => {
              setValue('')
              toaster.success({ title: `Saved: ${kg(parsed)}` })
            },
            onError: (error) => toaster.error({ title: 'Could not save the weight', description: error.message }),
          },
        )
      }}
    >
      <HStack>
        <Input
          aria-label="Weight today in kg"
          placeholder={current !== undefined ? `Today: ${kg(current)}` : 'Today, e.g. 82,4'}
          inputMode="decimal"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          maxW="44"
        />
        <Text color="fg.muted">kg</Text>
        <Button type="submit" colorPalette="teal" disabled={!valid} loading={save.isPending}>
          {current !== undefined ? 'Update' : 'Save'}
        </Button>
      </HStack>
    </form>
  )
}

function WeightChart({ weights }: { weights: WeightPoint[] }) {
  const chart = useChart({
    data: weights.map((p) => ({ day: formatDay(p.date), weight: p.weight })),
    series: [{ name: 'weight', color: 'teal.solid' }],
  })
  if (weights.length < 2) return null
  return (
    <Stack>
      <Chart.Root maxH="2xs" chart={chart}>
        <LineChart data={chart.data} margin={{ left: -10, right: 10 }}>
          <CartesianGrid stroke={chart.color('border')} vertical={false} />
          <XAxis dataKey={chart.key('day')} stroke={chart.color('border')} tickLine={false} />
          <YAxis stroke={chart.color('border')} tickLine={false} domain={['dataMin - 1', 'dataMax + 1']} />
          <Tooltip animationDuration={100} cursor={false} content={<Chart.Tooltip />} />
          {chart.series.map((item) => (
            <Line
              key={item.name}
              type="monotone"
              isAnimationActive={false}
              dataKey={chart.key(item.name)}
              stroke={chart.color(item.color)}
              strokeWidth={2}
              dot={{ r: 2 }}
            />
          ))}
        </LineChart>
      </Chart.Root>
    </Stack>
  )
}
