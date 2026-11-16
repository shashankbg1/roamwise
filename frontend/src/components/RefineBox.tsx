import { useState, type FormEvent } from 'react'

const EXAMPLES = ['Make day 2 cheaper', 'More relaxed', 'Add more to day 1']

interface Props {
  busy: boolean
  usingMock: boolean
  onRefine: (message: string) => void
}

export default function RefineBox({ busy, usingMock, onRefine }: Props) {
  const [message, setMessage] = useState('')

  const send = (text: string) => {
    const trimmed = text.trim()
    if (trimmed.length < 2 || busy) return
    onRefine(trimmed)
    setMessage('')
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    send(message)
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-slate-900">Change this plan</h3>
      <form onSubmit={submit} className="mt-2 flex gap-2">
        <label htmlFor="refine-message" className="sr-only">
          What should change
        </label>
        <input
          id="refine-message"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Tell the planner what to change"
          maxLength={500}
          className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-teal-600 focus:ring-2 focus:ring-teal-600/30 focus:outline-none"
        />
        <button
          type="submit"
          disabled={busy || message.trim().length < 2}
          className="rounded-md bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {busy ? 'Updating…' : 'Update'}
        </button>
      </form>
      <div className="mt-2 flex flex-wrap gap-2">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            disabled={busy}
            onClick={() => send(example)}
            className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-700 hover:border-teal-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {example}
          </button>
        ))}
      </div>
      {usingMock && (
        <p className="mt-2 text-xs text-slate-500">
          The rule-based stand-in only understands requests like these. A real model takes free
          text.
        </p>
      )}
    </section>
  )
}
