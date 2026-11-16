import { useCallback, useEffect, useRef, useState } from 'react'
import { deleteTrip, getTrip, listTrips, planTrip, refineTrip } from './api/client'
import type { AgentEvent, Itinerary, TripRequest, TripSummary } from './api/types'
import AgentFeed from './components/AgentFeed'
import ItineraryView from './components/ItineraryView'
import RefineBox from './components/RefineBox'
import SavedTrips from './components/SavedTrips'
import TripForm from './components/TripForm'

type Run = (onEvent: (event: AgentEvent) => void, signal: AbortSignal) => Promise<void>

export default function App() {
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [itinerary, setItinerary] = useState<Itinerary | null>(null)
  const [trips, setTrips] = useState<TripSummary[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abort = useRef<AbortController | null>(null)

  const refreshTrips = useCallback(async () => {
    try {
      setTrips(await listTrips())
    } catch {
      // The list is a convenience; a failure here should not hide the planner.
    }
  }, [])

  useEffect(() => {
    let alive = true
    listTrips()
      .then((saved) => {
        if (alive) setTrips(saved)
      })
      .catch(() => {})
    return () => {
      alive = false
      abort.current?.abort()
    }
  }, [])

  /** Run a streaming agent job and feed its events into the page. */
  const runJob = async (run: Run) => {
    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller
    setEvents([])
    setError(null)
    setRunning(true)
    let finished = false
    try {
      await run((event) => {
        if (event.type === 'final' && event.data) {
          finished = true
          setItinerary(event.data)
        } else if (event.type === 'error') {
          finished = true
          setError(event.message)
        } else {
          setEvents((current) => [...current, event])
        }
      }, controller.signal)
      if (!finished) setError('The connection closed before the plan was finished. Try again.')
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : 'Something went wrong. Try again.')
      }
    } finally {
      if (abort.current === controller) setRunning(false)
      void refreshTrips()
    }
  }

  const plan = (request: TripRequest) => {
    setItinerary(null)
    void runJob((onEvent, signal) => planTrip(request, onEvent, signal))
  }

  const refine = (message: string) => {
    if (!itinerary) return
    const tripId = itinerary.id
    void runJob((onEvent, signal) => refineTrip(tripId, message, onEvent, signal))
  }

  const open = async (id: string) => {
    setError(null)
    setEvents([])
    try {
      setItinerary(await getTrip(id))
    } catch (err) {
      setError(err instanceof Error ? err.message : "That trip couldn't be opened.")
    }
  }

  const remove = async (id: string) => {
    try {
      await deleteTrip(id)
      if (itinerary?.id === id) setItinerary(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "That trip couldn't be deleted.")
    }
    void refreshTrips()
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-baseline gap-3 px-4 py-4">
          <h1 className="text-xl font-semibold tracking-tight">Roamwise</h1>
          <p className="text-sm text-slate-500">
            A team of agents plans your trip while you watch.
          </p>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-6 px-4 py-6 lg:grid-cols-[20rem_1fr]">
        <aside className="flex flex-col gap-6">
          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <TripForm busy={running} onSubmit={plan} />
          </section>
          <SavedTrips
            trips={trips}
            activeId={itinerary?.id ?? null}
            disabled={running}
            onOpen={open}
            onDelete={remove}
          />
        </aside>

        <div className="flex min-w-0 flex-col gap-4">
          {error && (
            <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
              {error}
            </p>
          )}
          <AgentFeed events={events} running={running} />
          {itinerary ? (
            <>
              <RefineBox
                busy={running}
                usingMock={itinerary.llm_provider === 'mock'}
                onRefine={refine}
              />
              <ItineraryView itinerary={itinerary} />
            </>
          ) : (
            !running && (
              <p className="rounded-lg border border-dashed border-slate-300 px-4 py-10 text-center text-sm text-slate-500">
                Fill in the form and choose Plan trip. The researcher, planner, budget checker and
                critic will work through it here, then your day-by-day plan appears.
              </p>
            )
          )}
        </div>
      </main>
    </div>
  )
}
