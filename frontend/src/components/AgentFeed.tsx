import type { AgentEvent, AgentName } from '../api/types'

const AGENTS: { name: AgentName; label: string; job: string }[] = [
  { name: 'researcher', label: 'Researcher', job: 'Finds the place, weather and sights' },
  { name: 'planner', label: 'Planner', job: 'Arranges sights into days' },
  { name: 'budget', label: 'Budget checker', job: 'Adds up the costs' },
  { name: 'critic', label: 'Critic', job: 'Reviews the plan and can send it back' },
]

type Phase = 'idle' | 'working' | 'done'

function phaseOf(agent: AgentName, events: AgentEvent[]): { phase: Phase; latest: string } {
  let phase: Phase = 'idle'
  let latest = ''
  for (const event of events) {
    if (event.agent !== agent) continue
    phase = event.type === 'agent_done' ? 'done' : 'working'
    latest = event.message
  }
  return { phase, latest }
}

const DOT: Record<Phase, string> = {
  idle: 'bg-slate-300',
  working: 'bg-amber-500 animate-pulse',
  done: 'bg-teal-600',
}

interface Props {
  events: AgentEvent[]
  running: boolean
}

export default function AgentFeed({ events, running }: Props) {
  const runs = events.filter((e) => e.agent === 'planner' && e.type === 'agent_done').length
  return (
    <section aria-label="Agent activity" className="rounded-lg border border-slate-200 bg-white">
      <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-900">Agent activity</h2>
        <span className="text-xs text-slate-500">
          {running ? 'Working…' : events.length ? 'Finished' : 'Waiting for a request'}
        </span>
      </header>
      <ol className="divide-y divide-slate-100">
        {AGENTS.map(({ name, label, job }) => {
          const { phase, latest } = phaseOf(name, events)
          return (
            <li key={name} className="flex gap-3 px-4 py-3">
              <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${DOT[phase]}`} />
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-900">
                  {label}
                  {name === 'planner' && runs > 1 && (
                    <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-xs font-normal text-amber-800">
                      {runs - 1} revision{runs > 2 ? 's' : ''}
                    </span>
                  )}
                </p>
                <p className="text-sm break-words text-slate-600">{latest || job}</p>
              </div>
            </li>
          )
        })}
      </ol>
      {events.length > 0 && (
        <details className="border-t border-slate-200 px-4 py-3">
          <summary className="cursor-pointer text-xs font-medium text-slate-600">
            Full log ({events.length} steps)
          </summary>
          <ol className="mt-2 flex flex-col gap-1 font-mono text-xs text-slate-600">
            {events.map((event, index) => (
              <li key={index} className="break-words">
                <span className="text-slate-400">{String(index + 1).padStart(2, '0')}</span>{' '}
                <span className="text-teal-700">{event.agent}</span>{' '}
                {event.type === 'tool' ? '↳ ' : ''}
                {event.message}
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  )
}
