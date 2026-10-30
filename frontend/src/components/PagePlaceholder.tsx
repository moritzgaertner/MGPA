import { Center, Heading, Stack, Text } from '@chakra-ui/react'

type PagePlaceholderProps = {
  title: string
  description: string
}

/** Centered title + hint for pages whose real content comes in a later step. */
export function PagePlaceholder({ title, description }: PagePlaceholderProps) {
  return (
    <Center h="full" p="6">
      <Stack textAlign="center" gap="2" maxW="md">
        <Heading size="2xl">{title}</Heading>
        <Text color="fg.muted">{description}</Text>
      </Stack>
    </Center>
  )
}
