const SYMBOLS = { INR: '₹', USD: '$', EUR: '€', GBP: '£', JPY: '¥' }

export function formatMoney(value, currency = 'INR', { compact = false } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  try {
    return new Intl.NumberFormat(currency === 'INR' ? 'en-IN' : 'en-US', {
      style: 'currency',
      currency,
      notation: compact ? 'compact' : 'standard',
      maximumFractionDigits: compact ? 1 : 2,
    }).format(value)
  } catch {
    return `${SYMBOLS[currency] || currency + ' '}${Number(value).toLocaleString()}`
  }
}

export const formatNumber = (v, opts = {}) =>
  v === null || v === undefined ? '—' : new Intl.NumberFormat('en-IN', opts).format(v)

export function formatPeriod(iso, granularity) {
  if (!iso) return ''
  const d = new Date(iso + 'T00:00:00')
  if (granularity === 'month') return d.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

/** Inclusive end date of a trend bucket, used when drilling into a period. */
export function periodEnd(iso, granularity) {
  const d = new Date(iso + 'T00:00:00')
  if (granularity === 'week') d.setDate(d.getDate() + 6)
  else if (granularity === 'month') { d.setMonth(d.getMonth() + 1); d.setDate(0) }
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export const STATUS_COLORS = {
  Delivered: '#22c55e',
  Delayed: '#ff5630',
  'In Transit': '#00b8d9',
  Pending: '#ffab00',
  Cancelled: '#919eab',
}
export const SERIES = ['#4f46e5', '#0ea5e9', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#14b8a6', '#f97316']
