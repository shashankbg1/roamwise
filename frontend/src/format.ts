const usd = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

export const money = (value: number): string => usd.format(value)

/** Format an ISO date (YYYY-MM-DD) without shifting it across time zones. */
export function formatDate(iso: string, options: Intl.DateTimeFormatOptions): string {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString('en-US', options)
}

export function isoDaysFromNow(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() + days)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export const titleCase = (text: string): string =>
  text.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
