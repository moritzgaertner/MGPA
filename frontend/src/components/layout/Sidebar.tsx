import { Box, Button, Flex, HStack, IconButton, Stack, Text } from '@chakra-ui/react'
import { Link, type LinkProps, useNavigate } from '@tanstack/react-router'
import { LuActivity, LuBookOpen, LuDumbbell, LuLogOut, LuMessageSquare, LuPlus, LuStickyNote } from 'react-icons/lu'

import { useLogout } from '@/api/auth'
import { ColorModeButton } from '@/components/ui/color-mode'

import { ConversationList } from './ConversationList'

// Main sections of the app. `to` is type-checked against the routes in src/routes.
const NAV_ITEMS: { label: string; to: LinkProps['to']; icon: typeof LuMessageSquare }[] = [
  { label: 'Chat', to: '/chat', icon: LuMessageSquare },
  { label: 'Training', to: '/training', icon: LuDumbbell },
  { label: 'Tracking', to: '/tracking', icon: LuActivity },
  { label: 'Notes', to: '/notes', icon: LuStickyNote },
  { label: 'Knowledge', to: '/knowledge', icon: LuBookOpen },
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

      {/* asChild: render Chakra's button styles on the router's <Link> (a real <a> tag). */}
      <Button asChild colorPalette="teal">
        <Link to="/chat" onClick={onNavigate}>
          <LuPlus /> New chat
        </Link>
      </Button>

      <Stack as="nav" gap="1">
        {NAV_ITEMS.map(({ label, to, icon: Icon }) => (
          <Button
            key={label}
            asChild
            variant="ghost"
            justifyContent="flex-start"
            // The router marks the link of the open page with aria-current="page".
            _currentPage={{ bg: 'bg.emphasized', fontWeight: 'semibold' }}
          >
            <Link to={to} onClick={onNavigate}>
              <Icon /> {label}
            </Link>
          </Button>
        ))}
      </Stack>

      <Box flex="1" overflowY="auto">
        <Text fontSize="xs" fontWeight="semibold" color="fg.muted" textTransform="uppercase" px="2" mb="2">
          Conversations
        </Text>
        <ConversationList onNavigate={onNavigate} />
      </Box>

      <HStack justify="space-between" px="2">
        <Text fontSize="xs" color="fg.muted">
          v0.1
        </Text>
        <HStack gap="0">
          <ColorModeButton />
          <LogoutButton />
        </HStack>
      </HStack>
    </Flex>
  )
}

function LogoutButton() {
  const logout = useLogout()
  const navigate = useNavigate()
  return (
    <IconButton
      aria-label="Sign out"
      variant="ghost"
      size="sm"
      loading={logout.isPending}
      onClick={() => logout.mutate(undefined, { onSettled: () => void navigate({ to: '/login' }) })}
    >
      <LuLogOut />
    </IconButton>
  )
}
