// Dashboard page: KPI cards, charts, top lists. All numbers come from GET /analytics/summary.
import { useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Link, useNavigate } from 'react-router-dom'
import FilterBar from '../components/FilterBar'
import { CategoryDrilldown } from '../components/Drilldowns'
import { CategoryPie, DeliveryChart, DeliveryDaysChart, RevenueTrendChart } from '../components/charts/Charts'
import { IconCart, IconClock, IconRupee, IconTruck } from '../components/icons'
import { Card, EmptyState, ErrorState, KpiCard, Segmented, Skeleton } from '../components/ui'
import { errorMessage, filterParams, useGetDataQualityQuery, useGetSummaryQuery } from '../services/api'
import { resetFilters, selectFilters, setDateRange, setGranularity, setMetric, setStatuses } from '../features/filters/filtersSlice'
import { formatMoney, formatNumber, periodEnd } from '../utils/format'

// Options for the toggle buttons
const VIEW_OPTIONS = [{ value: 'both', label: 'Both' }, { value: 'revenue', label: 'Revenue' }, { value: 'orders', label: 'Orders' }]
const PIE_OPTIONS = [{ value: 'revenue', label: 'Revenue' }, { value: 'orders', label: 'Orders' }]
const PERIOD_OPTIONS = [{ value: 'day', label: 'Daily' }, { value: 'week', label: 'Weekly' }, { value: 'month', label: 'Monthly' }]

export default function Dashboard() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const filters = useSelector(selectFilters)
  const [drillCategory, setDrillCategory] = useState(null) // category whose products are shown in a popup
  const [pieMetric, setPieMetric] = useState('revenue')

  // Fetch the data. RTK Query gives us loading / error states and refetches when filters change.
  const { data, error, isLoading, refetch } = useGetSummaryQuery(filterParams(filters, { granularity: filters.granularity }))
  const { data: quality } = useGetDataQualityQuery()

  if (error) return <ErrorState message={errorMessage(error)} onRetry={refetch} />

  const currency = data?.currency.code ?? 'INR'
  const kpis = data?.kpis
  const change = data?.comparison?.change_pct ?? {} // % change vs previous period (only with a date range)
  const trend = data?.revenue_trend ?? []
  const granularity = data?.filters.granularity ?? 'day'
  const view = ['both', 'revenue', 'orders'].includes(filters.metric) ? filters.metric : 'both'
  const problems = quality?.checks.filter((check) => check.count > 0) ?? []

  return (
    <div className="page">
      <h1>Hi, Welcome back</h1>

      <FilterBar />

      {/* ---------- KPI cards ---------- */}
      <div className="kpi-grid">
        {isLoading ? [1, 2, 3, 4].map((i) => <Skeleton key={i} height={190} />) : (
          <>
            <KpiCard color="blue" icon={<IconCart />} label="Total Orders" value={formatNumber(kpis.total_orders)}
              change={change.total_orders} onClick={() => navigate('/orders')} />
            <KpiCard color="cyan" icon={<IconRupee />} label="Total Revenue"
              value={formatMoney(kpis.total_revenue, currency, { compact: true })} change={change.total_revenue} />
            <KpiCard color="yellow" icon={<IconTruck />} label="Avg Delivery (days)"
              value={kpis.avg_delivery_days ?? '—'} change={change.avg_delivery_days} goodWhenUp={false} />
            <KpiCard color="red" icon={<IconClock />} label="Delayed Orders" value={formatNumber(kpis.delayed_orders)}
              change={change.delayed_orders} goodWhenUp={false} onClick={() => navigate('/orders?delayed=1')} />
          </>
        )}
      </div>

      {!isLoading && kpis.total_orders === 0 ? (
        <Card>
          <EmptyState title="No orders to show">
            Clear the filters, or load data on the <Link to="/data">Data upload</Link> page.{' '}
            <button className="btn sm" onClick={() => dispatch(resetFilters())}>Clear filters</button>
          </EmptyState>
        </Card>
      ) : (
        <div className="grid-3col">
          {/* ---------- Revenue trend ---------- */}
          <Card className="span-2" title="Revenue trend"
            subtitle={change.total_revenue != null
              ? `(${change.total_revenue > 0 ? '+' : ''}${change.total_revenue}%) than previous period`
              : `${formatMoney(kpis?.total_revenue, currency)} total · click a point to zoom in`}
            actions={<Segmented label="View" options={VIEW_OPTIONS} value={view} onChange={(v) => dispatch(setMetric(v))} />}>
            {isLoading ? <Skeleton height={320} /> : (
              <RevenueTrendChart data={trend} view={view} currency={currency} granularity={granularity}
                onPointClick={(point) => dispatch(setDateRange({ startDate: point.period, endDate: periodEnd(point.period, granularity) }))} />
            )}
          </Card>

          {/* ---------- Category-wise revenue (click a slice to drill down) ---------- */}
          <Card title="Category-wise revenue" subtitle="Click a slice to see its products"
            actions={<Segmented label="Pie by" options={PIE_OPTIONS} value={pieMetric} onChange={setPieMetric} />}>
            {isLoading ? <Skeleton height={340} /> : (
              <CategoryPie data={data.category_revenue} metric={pieMetric} currency={currency} onSliceClick={setDrillCategory} />
            )}
          </Card>

          {/* ---------- Delivery performance ---------- */}
          <Card className="span-2" title="Delivery performance"
            subtitle={kpis ? `${kpis.delayed_pct}% of orders delayed (SLA ${data.sla_days} days) · click a colour to filter` : ''}
            actions={<Segmented label="Period" options={PERIOD_OPTIONS} value={granularity}
              onChange={(v) => dispatch(setGranularity(v))} />}>
            {isLoading ? <Skeleton height={300} /> : (
              <DeliveryChart data={trend} granularity={granularity} onStatusClick={(s) => dispatch(setStatuses([s]))} />
            )}
          </Card>

          {/* ---------- Delivery time ---------- */}
          <Card title="Delivery time" subtitle="Days from order to delivery">
            {isLoading ? <Skeleton height={240} /> : <DeliveryDaysChart data={data.delivery_days_distribution} sla={data.sla_days} />}
          </Card>

          {/* ---------- Top customers ---------- */}
          <Card title="Top customers" subtitle="By revenue">
            {isLoading ? <Skeleton height={260} /> : (
              <>
                <ul className="rank-list">
                  {data.top_customers.map((c) => (
                    <li key={c.customer_id}>
                      <span className="avatar">{c.customer_name[0]}</span>
                      <div className="rank-main"><strong>{c.customer_name}</strong><span className="muted tiny">{c.orders} orders</span></div>
                      <strong>{formatMoney(c.revenue, currency, { compact: true })}</strong>
                    </li>
                  ))}
                </ul>
                <Link className="check-all" to="/orders">Check all</Link>
              </>
            )}
          </Card>

          {/* ---------- Top products ---------- */}
          <Card title="Top products" subtitle="By revenue">
            {isLoading ? <Skeleton height={260} /> : (
              <>
                <ul className="rank-list">
                  {data.top_products.map((p, i) => (
                    <li key={p.product_id}>
                      <span className="rank-no">{i + 1}</span>
                      <div className="rank-main"><strong>{p.product_name}</strong><span className="muted tiny">{p.category}</span></div>
                      <strong>{formatMoney(p.revenue, currency, { compact: true })}</strong>
                    </li>
                  ))}
                </ul>
                <Link className="check-all" to="/orders">Check all</Link>
              </>
            )}
          </Card>

          {/* ---------- Data quality: what was wrong in the files and how it was handled ---------- */}
          <Card title="Data quality" subtitle="Issues found while cleaning the files">
            {problems.length === 0 ? <EmptyState title="All clean">No missing or inconsistent data.</EmptyState> : (
              <ul className="quality-list">
                {problems.map((p) => (
                  <li key={p.key}>
                    <span className="q-count">{p.count}</span>
                    <div><strong>{p.label}</strong><span className="muted tiny">{p.handling}</span></div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}

      {drillCategory && <CategoryDrilldown category={drillCategory} onClose={() => setDrillCategory(null)} />}
    </div>
  )
}
