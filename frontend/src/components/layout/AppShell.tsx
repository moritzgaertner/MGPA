import { Box, Drawer, Flex, IconButton, Portal, Text } from '@chakra-ui/react'
import { useState, type ReactNode } from 'react'
import { LuMenu } from 'react-icons/lu'

import { Sidebar } from './Sidebar'

type AppShellProps = {
  children: ReactNode
}

/**
 * Page frame: sidebar on the left, content on the right.
 * Below the "md" breakpoint (phones) the sidebar moves into a drawer behind a menu button.
 */
export function AppShell({ children }: AppShellProps) {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <Flex h="100dvh">
      {/* Desktop: always-visible sidebar */}
      <Box as="aside" w="72" flexShrink={0} borderRightWidth="1px" display={{ base: 'none', md: 'block' }}>
        <Sidebar />
      </Box>

      {/* Mobile: the same sidebar inside a slide-in drawer */}
      <Drawer.Root open={menuOpen} onOpenChange={(details) => setMenuOpen(details.open)} placement="start">
        <Portal>
          <Drawer.Backdrop />
          <Drawer.Positioner>
            <Drawer.Content maxW="72">
              <Sidebar onNavigate={() => setMenuOpen(false)} />
            </Drawer.Content>
          </Drawer.Positioner>
        </Portal>
      </Drawer.Root>

      <Flex direction="column" flex="1" minW="0">
        {/* Mobile-only top bar with the menu button */}
        <Flex
          as="header"
          display={{ base: 'flex', md: 'none' }}
          align="center"
          gap="2"
          px="3"
          py="2"
          borderBottomWidth="1px"
        >
          <IconButton aria-label="Open menu" variant="ghost" size="sm" onClick={() => setMenuOpen(true)}>
            <LuMenu />
          </IconButton>
          <Text fontWeight="semibold">MGPA</Text>
        </Flex>

        <Box as="main" flex="1" overflowY="auto">
          {children}
        </Box>
      </Flex>
    </Flex>
  )
}
