import { Box, Heading, Stack, Tabs, Text } from '@chakra-ui/react'
import { createFileRoute } from '@tanstack/react-router'

import { PlanTab } from '@/components/training/PlanTab'
import { ProgressTab } from '@/components/training/ProgressTab'
import { SessionsTab } from '@/components/training/SessionsTab'

export const Route = createFileRoute('/training')({
  component: TrainingPage,
})

function TrainingPage() {
  return (
    <Box maxW="4xl" mx="auto" p={{ base: '4', md: '8' }}>
      <Stack gap="1" mb="4">
        <Heading size="2xl">Training</Heading>
        <Text color="fg.muted" fontSize="sm">
          Log workouts in the chat (“BP 77, Skull 35”) — they appear here after you confirm them.
        </Text>
      </Stack>
      <Tabs.Root defaultValue="plan" lazyMount>
        <Tabs.List>
          <Tabs.Trigger value="plan">Plan</Tabs.Trigger>
          <Tabs.Trigger value="sessions">Sessions</Tabs.Trigger>
          <Tabs.Trigger value="progress">Progress</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="plan">
          <PlanTab />
        </Tabs.Content>
        <Tabs.Content value="sessions">
          <SessionsTab />
        </Tabs.Content>
        <Tabs.Content value="progress">
          <ProgressTab />
        </Tabs.Content>
      </Tabs.Root>
    </Box>
  )
}
