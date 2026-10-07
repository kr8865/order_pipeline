import { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useSearchParams } from 'react-router-dom'
import FilterBar from '../components/FilterBar'
import { OrderDetailModal } from '../components/Drilldowns'
import { Card, EmptyState, ErrorState, Loader, Pagination, StatusBadge } from '../components/ui'
import { errorMessage, filterParams, useGetOrdersQuery } from '../services/api'
import { selectFilters, setCategories } from '../features/filters/filtersSlice'
import { formatMoney } from '../utils/format'

const COLUMNS = [
  { key: 'order_id', label: 'Order', sortable: true },
  { key: 'order_date', label: 'Date', sortable: true },
  { key: 'customer_name', label: 'Customer', sortable: true },
  { key: 'categories', label: 'Categories' },
  { key: 'item_count', label: 'Units', num: true },
  { key: 'order_value', label: 'Order value', sortable: true, num: true },
  { key: 'delivery_days', label: 'Days', sortable: true, num: true },
  { key: 'delivery_status', label: 'Status' },
]

function useDebounced(value, ms = 350) {
  const [v, setV] = useState(value)
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t) }, [value, ms])
  return v
}

export default function Orders() {
  const f = useSelector(selectFilters)
  const dispatch = useDispatch()
  const [params, setParams] = useSearchParams()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [sort, setSort] = useState({ key: 'order_date', dir: 'desc' })
  const [search, setSearch] = useState(params.get('search') ?? '') // filled from the top-bar search
  const [selected, setSelected] = useState(null)
  const delayedOnly = params.get('delayed') === '1'
  const q = useDebounced(search)

  // Deep links from dashboard drill-downs: /orders?category=Electronics, /orders?delayed=1
  useEffect(() => {
    const cat = params.get('category')
    if (cat) {
      dispatch(setCategories([cat]))
      params.delete('category')
      setParams(params, { replace: true })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // When a new search comes from the top bar, show it in the search box.
  const urlSearch = params.get('search') ?? ''
  useEffect(() => setSearch(urlSearch), [urlSearch])

  useEffect(() => setPage(1), [f, q, delayedOnly, pageSize, sort])

  const invalidRange = f.startDate && f.endDate && f.startDate > f.endDate
  const { data, error, isLoading, isFetching, refetch } = useGetOrdersQuery(filterParams(f, {
    page, page_size: pageSize, sort: sort.key, order: sort.dir, search: q || undefined,
    delayed_only: delayedOnly || undefined,
  }), { skip: invalidRange })
  const cur = data?.currency?.code || f.currency

  const toggleSort = (key) =>
    setSort((s) => ({ key, dir: s.key === key && s.dir === 'desc' ? 'asc' : 'desc' }))

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Orders</h1><p className="muted">Flattened orders joined with products and shipments. Click a row for details.</p></div>
      </div>
      <FilterBar />
      <Card title="All orders" actions={
        <div className="row gap-s wrap">
          <label className="toggle">
            <input type="checkbox" checked={delayedOnly} onChange={(e) => {
              if (e.target.checked) params.set('delayed', '1'); else params.delete('delayed')
              setParams(params, { replace: true })
            }} /> Delayed only
          </label>
          <input type="search" placeholder="Search order, customer, product…" value={search}
            onChange={(e) => setSearch(e.target.value)} className="search" aria-label="Search orders" />
        </div>
      }>
        {error && <ErrorState message={errorMessage(error)} onRetry={refetch} />}
        {isLoading && <Loader block />}
        {data && (data.data.length === 0 ? <EmptyState title="No orders found">Adjust the filters or search.</EmptyState> : (
          <div className={`table-wrap ${isFetching ? 'dim' : ''}`}>
            <table className="table hover">
              <thead>
                <tr>{COLUMNS.map((c) => (
                  <th key={c.key} className={`${c.num ? 'num' : ''} ${c.sortable ? 'sortable' : ''}`}
                    onClick={c.sortable ? () => toggleSort(c.key) : undefined}
                    aria-sort={sort.key === c.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : undefined}>
                    {c.label}{sort.key === c.key && <span className="sort-ind">{sort.dir === 'asc' ? ' ▲' : ' ▼'}</span>}
                  </th>
                ))}</tr>
              </thead>
              <tbody>
                {data.data.map((o) => (
                  <tr key={o.order_id} onClick={() => setSelected(o.order_id)} tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && setSelected(o.order_id)}>
                    <td data-label="Order"><strong>#{o.order_id}</strong></td>
                    <td data-label="Date">{o.order_date || <span className="muted">—</span>}</td>
                    <td data-label="Customer">{o.customer_name}</td>
                    <td data-label="Categories">{o.categories.join(', ')}</td>
                    <td data-label="Units" className="num">{o.item_count}</td>
                    <td data-label="Value" className="num">{formatMoney(o.order_value, cur)}</td>
                    <td data-label="Days" className="num">{o.delivery_days ?? '—'}</td>
                    <td data-label="Status"><StatusBadge status={o.delivery_status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
        <Pagination pagination={data?.pagination} onPage={setPage} onPageSize={setPageSize} />
      </Card>
      {selected && <OrderDetailModal orderId={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
