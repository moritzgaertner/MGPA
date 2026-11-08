import { ApiError } from './client'

/*
 * Server-Sent Events emitted by POST /chat. They mirror the Chat*Event models in
 * backend/src/mgpa_backend/schemas.py — FastAPI documents the stream only as
 * "text/event-stream", so these types are not part of the generated schema.
 */
export type ChatStreamEvent =
  | { event: 'start'; data: { conversation_id: number } }
  | { event: 'delta'; data: { text: string } }
  | { event: 'done'; data: { message_id: number; input_tokens: number; output_tokens: number } }
  | { event: 'error'; data: { detail: string } }

/**
 * Send one chat message and yield the answer's events as they arrive.
 *
 * The browser's built-in EventSource only supports GET, but /chat is a POST with a JSON body —
 * so we read the response body as a stream and parse the SSE format ourselves:
 * blocks separated by a blank line, each with "event: <name>" and "data: <json>" lines.
 */
export async function* streamChat(
  body: { conversation_id: number | null; message: string },
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal,
  })
  // Errors before the stream starts (404 unknown conversation, 422 invalid input) are normal
  // HTTP errors with a JSON body.
  if (!response.ok || !response.body) {
    const detail = await response.json().then((json) => json.detail, () => undefined)
    throw new ApiError(response.status, detail)
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    // Network chunks don't respect event boundaries: process only complete blocks and keep
    // the (possibly half-received) rest in the buffer for the next chunk.
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      const event = parseBlock(block)
      if (event) yield event
    }
  }
}

function parseBlock(block: string): ChatStreamEvent | null {
  let event = ''
  let data = ''
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data += line.slice(5).trim()
    // Lines starting with ":" are keep-alive comments — ignored.
  }
  if (!event || !data) return null
  return { event, data: JSON.parse(data) } as ChatStreamEvent
}
