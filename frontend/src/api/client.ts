import createClient from 'openapi-fetch'

import type { components, paths } from './schema'

/**
 * Typed HTTP client for the MGPA backend. `paths` is generated from the backend's OpenAPI
 * schema (npm run api:types), so URLs, request bodies and responses are all type-checked.
 *
 * All requests go to "/api/...": in development Vite forwards them to the backend
 * (vite.config.ts), in production Caddy will do the same.
 */
export const api = createClient<paths>({ baseUrl: '/api' })

// Shorter names for the generated response types used across the app.
type Schemas = components['schemas']
export type Conversation = Schemas['ConversationRead']
export type ConversationDetail = Schemas['ConversationDetail']
export type Message = Schemas['MessageRead']
export type Note = Schemas['NoteRead']

/** Error thrown for any non-2xx response, carrying the backend's `detail` message. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `Request failed with status ${status}`)
    this.status = status
  }
}

/** Turn openapi-fetch's { data, error, response } result into "data or throw". */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    const detail = (result.error as { detail?: unknown } | undefined)?.detail
    throw new ApiError(result.response.status, detail)
  }
  return result.data as T
}
