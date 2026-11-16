import type { Activity, DayPlan, Itinerary } from '../api/types'
import { formatDate, money, titleCase } from '../format'

const SLOT_LABEL = { morning: 'Morning', afternoon: 'Afternoon', evening: 'Evening' } as const

function mapUrl(activity: Activity): string | null {
  if (activity.latitude === null || activity.longitude === null) return null
  const { latitude: lat, longitude: lon } = activity
  return `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=16/${lat}/${lon}`
}

function WeatherChip({ day }: { day: DayPlan }) {
  const w = day.weather
  if (!w || w.source === 'unavailable') {
    return <span className="text-xs text-slate-400">No weather data</span>
  }
  const temps =
    w.temp_max_c !== null && w.temp_min_c !== null
      ? ` · ${Math.round(w.temp_min_c)}–${Math.round(w.temp_max_c)}°C`
      : ''
  return (
    <span
      className="rounded-full bg-sky-50 px-2.5 py-1 text-xs text-sky-900"
      title={w.source === 'typical' ? 'Based on the same dates last year' : 'Forecast'}
    >
      {w.summary}
      {temps}
      {w.source === 'typical' ? ' · typical' : ''}
    </span>
  )
}

function DayCard({ day, number }: { day: DayPlan; number: number }) {
  const cost = day.activities.reduce((sum, a) => sum + a.est_cost_usd, 0)
  return (
    <article className="rounded-lg border border-slate-200 bg-white">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
        <div>
          <p className="text-xs font-medium tracking-wide text-teal-700 uppercase">
            Day {number} · {formatDate(day.date, { weekday: 'short', month: 'short', day: 'numeric' })}
          </p>
          <h3 className="text-base font-semibold text-slate-900">{day.theme}</h3>
        </div>
        <WeatherChip day={day} />
      </header>
      <ul className="divide-y divide-slate-100">
        {day.activities.map((activity, index) => {
          const url = mapUrl(activity)
          return (
            <li key={index} className="grid grid-cols-[5.5rem_1fr_auto] gap-3 px-4 py-3">
              <span className="pt-0.5 text-xs font-medium text-slate-500">
                {SLOT_LABEL[activity.slot]}
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium break-words text-slate-900">{activity.title}</p>
                <p className="text-xs text-slate-500">
                  {titleCase(activity.category)}
                  {url && (
                    <>
                      {' · '}
                      <a
                        href={url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-teal-700 underline hover:text-teal-900"
                      >
                        Map
                      </a>
                    </>
                  )}
                </p>
                {activity.notes && <p className="mt-1 text-xs text-slate-600">{activity.notes}</p>}
              </div>
              <span className="text-sm text-slate-700 tabular-nums">
                {activity.est_cost_usd > 0 ? money(activity.est_cost_usd) : 'Free'}
              </span>
            </li>
          )
        })}
      </ul>
      <footer className="flex justify-between border-t border-slate-200 px-4 py-2 text-xs text-slate-500">
        <span>Day total</span>
        <span className="font-medium text-slate-700 tabular-nums">{money(cost)}</span>
      </footer>
    </article>
  )
}

function BudgetPanel({ itinerary }: { itinerary: Itinerary }) {
  const { budget } = itinerary
  const share = Math.min(100, (budget.total_estimated_usd / budget.budget_usd) * 100)
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-900">Budget</h3>
        <p className="text-sm text-slate-700 tabular-nums">
          <span className="font-semibold">{money(budget.total_estimated_usd)}</span> of{' '}
          {money(budget.budget_usd)}
        </p>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full ${budget.within_budget ? 'bg-teal-600' : 'bg-red-600'}`}
          style={{ width: `${share}%` }}
        />
      </div>
      <ul className="mt-3 flex flex-col gap-1 text-sm text-slate-600">
        {budget.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </section>
  )
}

function ReviewPanel({ itinerary }: { itinerary: Itinerary }) {
  const { critique, revisions } = itinerary
  const tone = critique.approved
    ? 'border-teal-200 bg-teal-50 text-teal-900'
    : 'border-amber-300 bg-amber-50 text-amber-900'
  return (
    <section className={`rounded-lg border p-4 ${tone}`}>
      <h3 className="text-sm font-semibold">
        {critique.approved ? 'Approved by the critic' : 'The critic still has concerns'}
        {revisions > 0 && (
          <span className="font-normal">
            {' '}
            after {revisions} revision{revisions > 1 ? 's' : ''}
          </span>
        )}
      </h3>
      {(critique.issues.length > 0 || critique.suggestions.length > 0) && (
        <ul className="mt-2 flex list-disc flex-col gap-1 pl-5 text-sm">
          {critique.issues.map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
          {critique.suggestions.map((tip) => (
            <li key={tip}>{tip}</li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function ItineraryView({ itinerary }: { itinerary: Itinerary }) {
  const { location, request } = itinerary
  const place = location.country ? `${location.name}, ${location.country}` : location.name
  return (
    <div className="flex flex-col gap-4">
      <header>
        <h2 className="text-2xl font-semibold text-slate-900">{place}</h2>
        <p className="text-sm text-slate-600">
          {formatDate(request.start_date, { month: 'short', day: 'numeric' })} to{' '}
          {formatDate(request.end_date, { month: 'short', day: 'numeric', year: 'numeric' })} ·{' '}
          {request.travelers} traveller{request.travelers > 1 ? 's' : ''} · {request.pace} pace
        </p>
        <p className="mt-2 text-sm text-slate-800">{itinerary.overview}</p>
        <p className="mt-1 text-sm text-slate-600">{itinerary.brief.weather_note}</p>
      </header>
      {itinerary.llm_provider === 'mock' && (
        <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
          Planned by the rule-based stand-in, not an AI model. Places and weather are real; the
          wording and choices are simple rules. Set a model provider in the backend to use Claude.
        </p>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <BudgetPanel itinerary={itinerary} />
        <ReviewPanel itinerary={itinerary} />
      </div>
      {itinerary.days.map((day, index) => (
        <DayCard key={day.date} day={day} number={index + 1} />
      ))}
    </div>
  )
}
