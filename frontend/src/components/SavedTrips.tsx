import type { TripSummary } from '../api/types'
import { formatDate, money } from '../format'

interface Props {
  trips: TripSummary[]
  activeId: string | null
  disabled: boolean
  onOpen: (id: string) => void
  onDelete: (id: string) => void
}

export default function SavedTrips({ trips, activeId, disabled, onOpen, onDelete }: Props) {
  return (
    <section aria-label="Saved trips">
      <h2 className="mb-2 text-sm font-semibold text-slate-900">Saved trips</h2>
      {trips.length === 0 ? (
        <p className="text-sm text-slate-500">Plans you create are saved here.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {trips.map((trip) => (
            <li
              key={trip.id}
              className={
                'flex items-center gap-2 rounded-md border px-3 py-2 ' +
                (trip.id === activeId ? 'border-teal-600 bg-teal-50' : 'border-slate-200 bg-white')
              }
            >
              <button
                type="button"
                disabled={disabled}
                onClick={() => onOpen(trip.id)}
                className="min-w-0 flex-1 text-left disabled:cursor-not-allowed"
              >
                <span className="block truncate text-sm font-medium text-slate-900">
                  {trip.destination}
                </span>
                <span className="block text-xs text-slate-500">
                  {formatDate(trip.start_date, { month: 'short', day: 'numeric' })} to{' '}
                  {formatDate(trip.end_date, { month: 'short', day: 'numeric' })} ·{' '}
                  {money(trip.total_estimated_usd)}
                </span>
              </button>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onDelete(trip.id)}
                aria-label={`Delete the ${trip.destination} trip`}
                className="rounded px-2 py-1 text-xs text-slate-500 hover:bg-red-50 hover:text-red-700 disabled:cursor-not-allowed"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
