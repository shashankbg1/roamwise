import type { AgentEvent, Itinerary, TripRequest, TripSummary } from './types'

/**
 * POST a JSON body and read the response as a stream of server-sent events.
 * EventSource only supports GET, so the stream is parsed by hand: events are separated by a
 * blank line and each carries one `data: {json}` line.
 */
async function streamPost(
  url: string,
  body: unknown,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok || !response.body) {
    throw new Error(await describeFailure(response))
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const chunk = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      for (const line of chunk.split('\n')) {
        if (line.startsWith('data: ')) onEvent(JSON.parse(line.slice(6)) as AgentEvent)
      }
      boundary = buffer.indexOf('\n\n')
    }
  }
}

async function describeFailure(response: Response): Promise<string> {
  try {
    const payload = await response.json()
    if (Array.isArray(payload.detail)) {
      // FastAPI validation errors: [{ msg: "Value error, end_date must not be before..." }]
      return payload.detail.map((d: { msg: string }) => d.msg.replace(/^Value error, /, '')).join('. ')
    }
    if (typeof payload.detail === 'string') return payload.detail
  } catch {
    // fall through to the generic message
  }
  return response.status >= 500
    ? "The server isn't responding. Check that the backend is running."
    : `Request failed (${response.status}).`
}

export function planTrip(
  request: TripRequest,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamPost('/api/trips', request, onEvent, signal)
}

export function refineTrip(
  tripId: string,
  message: string,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamPost(`/api/trips/${tripId}/refine`, { message }, onEvent, signal)
}

export async function listTrips(): Promise<TripSummary[]> {
  const response = await fetch('/api/trips')
  if (!response.ok) throw new Error(await describeFailure(response))
  return response.json()
}

export async function getTrip(tripId: string): Promise<Itinerary> {
  const response = await fetch(`/api/trips/${tripId}`)
  if (!response.ok) throw new Error(await describeFailure(response))
  return response.json()
}

export async function deleteTrip(tripId: string): Promise<void> {
  const response = await fetch(`/api/trips/${tripId}`, { method: 'DELETE' })
  if (!response.ok) throw new Error(await describeFailure(response))
}
