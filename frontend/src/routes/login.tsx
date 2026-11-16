import { Button, Card, Center, Field, Heading, Input, Stack, Text } from '@chakra-ui/react'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

import { useLogin } from '@/api/auth'
import { ApiError } from '@/api/client'

type LoginSearch = { redirect?: string }

export const Route = createFileRoute('/login')({
  // ?redirect=/training → after login, go back to where the user wanted to go.
  validateSearch: (search: Record<string, unknown>): LoginSearch => ({
    redirect: typeof search.redirect === 'string' ? search.redirect : undefined,
  }),
  component: LoginPage,
})

function LoginPage() {
  const { redirect } = Route.useSearch()
  const navigate = useNavigate()
  const login = useLogin()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const submit = () =>
    login.mutate(
      { username: username.trim(), password },
      {
        onSuccess: () => {
          // Only same-site paths, so a crafted link can't send the user to another website.
          const target = redirect?.startsWith('/') && !redirect.startsWith('//') ? redirect : '/chat'
          void navigate({ to: target, replace: true })
        },
      },
    )

  const error =
    login.error instanceof ApiError
      ? login.error.status === 429
        ? login.error.message
        : 'Wrong username or password.'
      : login.error
        ? 'Login failed — is the backend running?'
        : null

  return (
    <Center minH="100dvh" p="4" bg="bg.subtle">
      <Card.Root w="full" maxW="sm">
        <Card.Body>
          <form
            onSubmit={(event) => {
              event.preventDefault()
              submit()
            }}
          >
            <Stack gap="4">
              <Stack gap="1">
                <Heading size="xl">MGPA</Heading>
                <Text color="fg.muted" fontSize="sm">
                  Please sign in.
                </Text>
              </Stack>
              <Field.Root>
                <Field.Label>Username</Field.Label>
                <Input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  autoCapitalize="none"
                  autoFocus
                />
              </Field.Root>
              <Field.Root>
                <Field.Label>Password</Field.Label>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
              </Field.Root>
              {error && (
                <Text color="fg.error" fontSize="sm">
                  {error}
                </Text>
              )}
              <Button type="submit" colorPalette="teal" loading={login.isPending} disabled={!username || !password}>
                Sign in
              </Button>
            </Stack>
          </form>
        </Card.Body>
      </Card.Root>
    </Center>
  )
}
