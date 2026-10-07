// Chart components built with Recharts. Each chart gets its data and click handlers as props.
import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Pie, PieChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { formatMoney, formatPeriod, STATUS_COLORS } from '../../utils/format'

// Colours taken from the reference dashboard
export const COLORS = ['#2065d1', '#ffab00', '#00b8d9', '#ff5630', '#22c55e', '#8e33ff', '#ff7a45']
const axisStyle = { fontSize: 12, fill: '#919eab' }
// Grey legend text, like the reference dashboard
const legendText = (value) => <span style={{ color: '#637381', fontSize: 13 }}>{value}</span>

// Revenue trend: blue bars = number of orders, orange line = revenue (like "Website Visits").
// view: 'both' | 'revenue' | 'orders'
export function RevenueTrendChart({ data, view, currency, granularity, onPointClick }) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <ComposedChart data={data} onClick={(e) => e?.activePayload && onPointClick(e.activePayload[0].payload)}>
        <defs>
          <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ffab00" stopOpacity={0.25} />
            <stop offset="100%" stopColor="#ffab00" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef1f4" vertical={false} />
        <XAxis dataKey="period" tick={axisStyle} tickFormatter={(v) => formatPeriod(v, granularity)} axisLine={false} tickLine={false} />
        <YAxis yAxisId="revenue" hide={view === 'orders'} tick={axisStyle} axisLine={false} tickLine={false} width={70}
          tickFormatter={(v) => formatMoney(v, currency, { compact: true })} />
        <YAxis yAxisId="orders" hide={view === 'revenue'} orientation="right" tick={axisStyle} axisLine={false} tickLine={false} width={40} allowDecimals={false} />
        <Tooltip formatter={(value, name) => (name === 'Revenue' ? formatMoney(value, currency) : value)} />
        <Legend verticalAlign="top" align="right" iconType="circle" height={36} formatter={legendText} />
        {view !== 'revenue' && <Bar yAxisId="orders" dataKey="orders" name="Orders" fill="#2065d1" barSize={10} radius={[4, 4, 0, 0]} />}
        {view !== 'orders' && (
          <Area yAxisId="revenue" type="monotone" dataKey="revenue" name="Revenue" stroke="#ffab00" strokeWidth={3}
            fill="url(#revenueFill)" dot={false} />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  )
}

// Category share as a pie chart with % labels (like "Current Visits"). Click a slice to drill down.
export function CategoryPie({ data, metric, currency, onSliceClick }) {
  const valueKey = metric === 'orders' ? 'orders' : 'revenue'
  const total = data.reduce((sum, d) => sum + d[valueKey], 0)

  // Write the percentage inside each slice (skip very small slices)
  const renderLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, value }) => {
    const percent = (value / total) * 100
    if (percent < 6) return null
    const radius = innerRadius + (outerRadius - innerRadius) * 0.6
    const x = cx + radius * Math.cos((-midAngle * Math.PI) / 180)
    const y = cy + radius * Math.sin((-midAngle * Math.PI) / 180)
    return <text x={x} y={y} fill="#fff" fontSize={12} fontWeight={700} textAnchor="middle" dominantBaseline="central">{percent.toFixed(1)}%</text>
  }

  return (
    <ResponsiveContainer width="100%" height={340}>
      <PieChart>
        <Pie data={data} dataKey={valueKey} nameKey="category" outerRadius={110} stroke="#fff" strokeWidth={2}
          labelLine={false} label={renderLabel} onClick={(slice) => onSliceClick(slice.category)} style={{ cursor: 'pointer' }}>
          {data.map((d, i) => <Cell key={d.category} fill={COLORS[i % COLORS.length]} />)}
        </Pie>
        <Tooltip formatter={(value) => (valueKey === 'revenue' ? formatMoney(value, currency) : `${value} orders`)} />
        <Legend verticalAlign="bottom" iconType="circle" formatter={legendText} />
      </PieChart>
    </ResponsiveContainer>
  )
}

// Orders per period, stacked by delivery status (like "Visitors / Sales"). Click a colour to filter.
export function DeliveryChart({ data, granularity, onStatusClick }) {
  const statuses = ['Delivered', 'In Transit', 'Pending', 'Delayed']
  const rows = data.map((d) => ({ period: d.period, ...d.by_status }))
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={rows}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef1f4" vertical={false} />
        <XAxis dataKey="period" tick={axisStyle} tickFormatter={(v) => formatPeriod(v, granularity)} axisLine={false} tickLine={false} />
        <YAxis tick={axisStyle} allowDecimals={false} axisLine={false} tickLine={false} width={32} />
        <Tooltip cursor={{ fill: '#f4f6f8' }} labelFormatter={(v) => formatPeriod(v, 'day')} />
        <Legend verticalAlign="bottom" iconType="circle" formatter={legendText} />
        {statuses.map((status) => (
          <Bar key={status} dataKey={status} stackId="orders" fill={STATUS_COLORS[status]} barSize={16}
            onClick={() => onStatusClick(status)} style={{ cursor: 'pointer' }} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

// How many days deliveries took. Red bars are slower than the SLA.
export function DeliveryDaysChart({ data, sla }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef1f4" vertical={false} />
        <XAxis dataKey="days" tick={axisStyle} axisLine={false} tickLine={false} />
        <YAxis tick={axisStyle} allowDecimals={false} axisLine={false} tickLine={false} width={32} />
        <Tooltip formatter={(value) => [`${value} orders`, 'Orders']} labelFormatter={(d) => `${d} day(s)`} />
        <ReferenceLine x={sla} stroke="#ff5630" strokeDasharray="4 4" label={{ value: `SLA ${sla}d`, fill: '#ff5630', fontSize: 11, position: 'top' }} />
        <Bar dataKey="orders" radius={[4, 4, 0, 0]}>
          {data.map((d) => <Cell key={d.days} fill={d.late ? '#ff5630' : '#22c55e'} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
