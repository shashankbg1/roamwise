// These mirror the Pydantic models in backend/app/models/schemas.py.

export type Interest = 'history' | 'food' | 'nature' | 'art' | 'nightlife' | 'shopping'
export type Pace = 'relaxed' | 'balanced' | 'packed'
export type AgentName = 'researcher' | 'planner' | 'budget' | 'critic' | 'system'

export interface TripRequest {
  destination: string
  start_date: string
  end_date: string
  budget_usd: number
  travelers: number
  interests: Interest[]
  pace: Pace
}

export interface DayWeather {
  date: string
  temp_max_c: number | null
  temp_min_c: number | null
  precipitation_mm: number | null
  summary: string
  source: 'forecast' | 'typical' | 'unavailable'
}

export interface Activity {
  slot: 'morning' | 'afternoon' | 'evening'
  title: string
  place_name: string | null
  category: string
  latitude: number | null
  longitude: number | null
  est_cost_usd: number
  notes: string
}

export interface DayPlan {
  date: string
  theme: string
  activities: Activity[]
  weather: DayWeather | null
}

export interface BudgetReport {
  budget_usd: number
  total_estimated_usd: number
  per_day_usd: number[]
  by_category_usd: Record<string, number>
  within_budget: boolean
  notes: string[]
}

export interface Itinerary {
  id: string
  created_at: string
  request: TripRequest
  location: { name: string; country: string | null; latitude: number; longitude: number }
  overview: string
  brief: { summary: string; highlights: string[]; weather_note: string }
  days: DayPlan[]
  budget: BudgetReport
  critique: { approved: boolean; issues: string[]; suggestions: string[] }
  revisions: number
  llm_provider: string
}

export interface TripSummary {
  id: string
  destination: string
  start_date: string
  end_date: string
  total_estimated_usd: number
  created_at: string
}

export interface AgentEvent {
  type: 'status' | 'tool' | 'agent_done' | 'final' | 'error'
  agent: AgentName
  message: string
  data: Itinerary | null
}
