import { Box, Button, Flex, HStack, Stack, Text } from '@chakra-ui/react'
import { LuBookOpen, LuListTodo, LuMessageSquare, LuPlus, LuStickyNote } from 'react-icons/lu'

import { ColorModeButton } from '@/components/ui/color-mode'

// Main sections of the app. They become real links once the router is added (step 3).
const NAV_ITEMS = [
  { label: 'Chat', icon: LuMessageSquare },
  { label: 'Notes', icon: LuStickyNote },
  { label: 'Knowledge', icon: LuBookOpen },
  { label: 'Tasks', icon: LuListTodo },
]

type SidebarProps = {
  /** Called after any navigation click — the mobile drawer uses it to close itself. */
  onNavigate?: () => void
}

export function Sidebar({ onNavigate }: SidebarProps) {
  return (
    <Flex direction="column" h="full" p="3" gap="4" bg="bg.subtle">
      <Text fontSize="lg" fontWeight="bold" px="2">
        MGPA
      </Text>

      <Button colorPalette="teal" onClick={onNavigate}>
        <LuPlus /> New chat
      </Button>

      <Stack gap="1">
        {NAV_ITEMS.map(({ label, icon: Icon }) => (
          <Button key={label} variant="ghost" justifyContent="flex-start" onClick={onNavigate}>
            <Icon /> {label}
          </Button>
        ))}
      </Stack>

      {/* Conversation list: filled from the backend in step 4. */}
      <Box flex="1" overflowY="auto">
        <Text fontSize="xs" fontWeight="semibold" color="fg.muted" textTransform="uppercase" px="2" mb="2">
          Conversations
        </Text>
        <Text fontSize="sm" color="fg.muted" px="2">
          No conversations yet.
        </Text>
      </Box>

      <HStack justify="space-between" px="2">
        <Text fontSize="xs" color="fg.muted">
          v0.1
        </Text>
        <ColorModeButton />
      </HStack>
    </Flex>
  )
}
