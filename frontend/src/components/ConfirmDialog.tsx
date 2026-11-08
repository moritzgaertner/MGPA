import { Button, Dialog, Portal, Text } from '@chakra-ui/react'

type ConfirmDialogProps = {
  title: string
  message: string
  confirmLabel: string
  onConfirm: () => void
  onClose: () => void
  loading?: boolean
}

/** "Are you sure?" dialog for destructive actions (red confirm button). */
export function ConfirmDialog({ title, message, confirmLabel, onConfirm, onClose, loading }: ConfirmDialogProps) {
  return (
    <Dialog.Root open onOpenChange={(details) => !details.open && onClose()} placement="center" role="alertdialog">
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content>
            <Dialog.Header>
              <Dialog.Title>{title}</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <Text>{message}</Text>
            </Dialog.Body>
            <Dialog.Footer>
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button colorPalette="red" onClick={onConfirm} loading={loading}>
                {confirmLabel}
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  )
}
