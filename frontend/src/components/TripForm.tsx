import { useState, type FormEvent } from 'react'
import type { Interest, Pace, TripRequest } from '../api/types'
import { isoDaysFromNow } from '../format'

const INTERESTS: { value: Interest; label: string }[] = [
  { value: 'history', label: 'History' },
  { value: 'food', label: 'Food' },
  { value: 'nature', label: 'Nature' },
  { value: 'art', label: 'Art' },
  { value: 'nightlife', label: 'Nightlife' },
  { value: 'shopping', label: 'Shopping' },
]
const PACES: { value: Pace; label: string; hint: string }[] = [
  { value: 'relaxed', label: 'Relaxed', hint: '1 sight a day' },
  { value: 'balanced', label: 'Balanced', hint: '2 sights a day' },
  { value: 'packed', label: 'Packed', hint: '3 sights a day' },
]

const field =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 ' +
  'focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/30'
const label = 'flex flex-col gap-1 text-sm font-medium text-slate-700'

interface Props {
  busy: boolean
  onSubmit: (request: TripRequest) => void
}

export default function TripForm({ busy, onSubmit }: Props) {
  const [destination, setDestination] = useState('Lisbon')
  const [startDate, setStartDate] = useState(isoDaysFromNow(30))
  const [endDate, setEndDate] = useState(isoDaysFromNow(33))
  const [budget, setBudget] = useState(800)
  const [travelers, setTravelers] = useState(2)
  const [interests, setInterests] = useState<Interest[]>(['history', 'food', 'nature'])
  const [pace, setPace] = useState<Pace>('balanced')

  const toggle = (interest: Interest) =>
    setInterests((current) =>
      current.includes(interest) ? current.filter((i) => i !== interest) : [...current, interest],
    )

  const submit = (event: FormEvent) => {
    event.preventDefault()
    onSubmit({
      destination: destination.trim(),
      start_date: startDate,
      end_date: endDate,
      budget_usd: budget,
      travelers,
      interests,
      pace,
    })
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <label className={label}>
        Destination
        <input
          id="destination"
          className={field}
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          placeholder="City or town"
          required
          minLength={2}
          maxLength={80}
        />
      </label>

      <div className="grid grid-cols-2 gap-3">
        <label className={label}>
          From
          <input
            id="start-date"
            type="date"
            className={field}
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            required
          />
        </label>
        <label className={label}>
          To
          <input
            id="end-date"
            type="date"
            className={field}
            value={endDate}
            min={startDate}
            onChange={(e) => setEndDate(e.target.value)}
            required
          />
        </label>
        <label className={label}>
          Budget (USD)
          <input
            id="budget"
            type="number"
            className={field}
            value={budget}
            min={1}
            step={1}
            onChange={(e) => setBudget(Number(e.target.value))}
            required
          />
        </label>
        <label className={label}>
          Travellers
          <input
            id="travelers"
            type="number"
            className={field}
            value={travelers}
            min={1}
            max={12}
            onChange={(e) => setTravelers(Number(e.target.value))}
            required
          />
        </label>
      </div>
      <p className="-mt-2 text-xs text-slate-500">
        The budget covers activities and meals, not flights or accommodation.
      </p>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm font-medium text-slate-700">Interests</legend>
        <div className="flex flex-wrap gap-2">
          {INTERESTS.map(({ value, label: text }) => {
            const on = interests.includes(value)
            return (
              <button
                key={value}
                type="button"
                aria-pressed={on}
                onClick={() => toggle(value)}
                className={
                  'rounded-full border px-3 py-1 text-sm transition-colors ' +
                  (on
                    ? 'border-teal-700 bg-teal-700 text-white'
                    : 'border-slate-300 bg-white text-slate-700 hover:border-teal-600')
                }
              >
                {text}
              </button>
            )
          })}
        </div>
      </fieldset>

      <fieldset>
        <legend className="mb-2 text-sm font-medium text-slate-700">Pace</legend>
        <div className="grid grid-cols-3 gap-2">
          {PACES.map(({ value, label: text, hint }) => (
            <label
              key={value}
              className={
                'cursor-pointer rounded-md border px-2 py-2 text-center text-sm ' +
                (pace === value
                  ? 'border-teal-700 bg-teal-50 text-teal-900'
                  : 'border-slate-300 bg-white text-slate-700 hover:border-teal-600')
              }
            >
              <input
                type="radio"
                name="pace"
                value={value}
                checked={pace === value}
                onChange={() => setPace(value)}
                className="sr-only"
              />
              <span className="block font-medium">{text}</span>
              <span className="block text-xs text-slate-500">{hint}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <button
        type="submit"
        disabled={busy || interests.length === 0}
        className="rounded-md bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-400"
      >
        {busy ? 'Planning…' : 'Plan trip'}
      </button>
      {interests.length === 0 && (
        <p className="text-xs text-amber-700">Pick at least one interest.</p>
      )}
    </form>
  )
}
