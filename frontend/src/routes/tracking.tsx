import { Box, Heading, Stack, Text } from '@chakra-ui/react'
import { createFileRoute } from '@tanstack/react-router'

import { HabitsCard } from '@/components/tracking/HabitsCard'
import { WeightCard } from '@/components/tracking/WeightCard'

export const Route = createFileRoute('/tracking')({
  component: TrackingPage,
})

function TrackingPage() {
  return (
    <Box maxW="3xl" mx="auto" p={{ base: '4', md: '8' }}>
      <Stack gap="1" mb="4">
        <Heading size="2xl">Tracking</Heading>
        <Text color="fg.muted" fontSize="sm">
          Tick habits and enter your weight here — or tell the chat (“Gewicht 82,4”, “Habits: Lesen, Yoga”).
        </Text>
      </Stack>
      <Stack gap="4">
        <HabitsCard />
        <WeightCard />
      </Stack>
    </Box>
  )
}
