/* Small reusable presentational components. */
import { useEffect } from 'react'
import { STATUS_COLORS } from '../utils/format'

export function Card({ title, subtitle, actions, children, className = '' }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          <div>
            {title && <h3>{title}</h3>}
            {subtitle && <p className="muted small">{subtitle}</p>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  )
}

// KPI card like the brief's reference dashboard: coloured box, round icon, big centred number.
// `change` = % change vs the previous period (shown only when a date range is selected).
// goodWhenUp={false} makes an increase red (more delayed orders is bad).
export function KpiCard({ label, value, color, icon, change, goodWhenUp = true, onClick }) {
  const showChange = change !== null && change !== undefined
  const isGood = change === 0 || (change > 0) === goodWhenUp
  return (
    <div className={`kpi kpi-${color} ${onClick ? 'clickable' : ''}`} onClick={onClick}>
      <span className="kpi-icon">{icon}</span>
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
      {showChange && (
        <div className={`kpi-change ${isGood ? 'up' : 'down'}`}>
          {change > 0 ? '+' : ''}{change}% vs previous period
        </div>
      )}
    </div>
  )
}

export function Loader({ label = 'Loading…', block }) {
  return (
    <div className={`loader ${block ? 'block' : ''}`} role="status">
      <span className="spinner" /> {label}
    </div>
  )
}

export function Skeleton({ height = 120 }) {
  return <div className="skeleton" style={{ height }} />
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="error-state" role="alert">
      <strong>Something went wrong</strong>
      <p>{message}</p>
      {onRetry && <button className="btn" onClick={onRetry}>Try again</button>}
    </div>
  )
}

export function EmptyState({ title = 'No data', children }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      {children && <p className="muted">{children}</p>}
    </div>
  )
}

export function Segmented({ options, value, onChange, label }) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} role="radio" aria-checked={value === o.value}
          className={value === o.value ? 'on' : ''} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function StatusBadge({ status }) {
  const color = STATUS_COLORS[status] || '#64748b'
  return (
    <span className="badge" style={{ color, background: `${color}1a`, borderColor: `${color}55` }}>
      {status}
    </span>
  )
}

export function Modal({ title, onClose, children, wide }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = '' }
  }, [onClose])
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-label={title}>
        <header className="modal-head">
          <h3>{title}</h3>
          <button className="icon-btn" onClick={onClose} aria-label="Close">✕</button>
        </header>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}

export function Pagination({ pagination, onPage, onPageSize }) {
  if (!pagination) return null
  const { page, pages, total, page_size: size, has_prev: hasPrev, has_next: hasNext } = pagination
  const from = total ? (page - 1) * size + 1 : 0
  const to = Math.min(page * size, total)
  return (
    <div className="pagination">
      <span className="muted small">{from}–{to} of {total}</span>
      <div className="pager">
        <select value={size} onChange={(e) => onPageSize(Number(e.target.value))} aria-label="Rows per page">
          {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n} / page</option>)}
        </select>
        <button className="btn" disabled={!hasPrev} onClick={() => onPage(1)} aria-label="First page">«</button>
        <button className="btn" disabled={!hasPrev} onClick={() => onPage(page - 1)}>Prev</button>
        <span className="small">Page {page} / {pages}</span>
        <button className="btn" disabled={!hasNext} onClick={() => onPage(page + 1)}>Next</button>
        <button className="btn" disabled={!hasNext} onClick={() => onPage(pages)} aria-label="Last page">»</button>
      </div>
    </div>
  )
}
