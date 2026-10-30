import { Center, Heading, Stack, Text } from '@chakra-ui/react'

import { AppShell } from '@/components/layout/AppShell'

export default function App() {
  return (
    <AppShell>
      <Center h="full" p="6">
        <Stack textAlign="center" gap="2">
          <Heading size="2xl">What can I help with?</Heading>
          <Text color="fg.muted">The chat arrives in step 5 — this is the layout.</Text>
        </Stack>
      </Center>
    </AppShell>
  )
}
