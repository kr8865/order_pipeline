import { useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { errorMessage, filterParams, useGetCategoryQuery, useGetOrderQuery } from '../services/api'
import { selectFilters } from '../features/filters/filtersSlice'
import { formatMoney, formatNumber } from '../utils/format'
import { EmptyState, ErrorState, Loader, Modal, StatusBadge } from './ui'

export function CategoryDrilldown({ category, onClose }) {
  const f = useSelector(selectFilters)
  const navigate = useNavigate()
  const params = filterParams({ ...f, categories: [] })
  const { data, error, isFetching, refetch } = useGetCategoryQuery({ category, ...params })
  const cur = data?.currency?.code || f.currency

  return (
    <Modal title={`${category} — product breakdown`} onClose={onClose} wide>
      {isFetching && !data && <Loader block />}
      {error && <ErrorState message={errorMessage(error)} onRetry={refetch} />}
      {data && (
        <>
          <div className="mini-kpis">
            <div><span className="muted small">Revenue</span><strong>{formatMoney(data.revenue, cur)}</strong></div>
            <div><span className="muted small">Orders</span><strong>{formatNumber(data.orders)}</strong></div>
            <div><span className="muted small">Products</span><strong>{data.products.length}</strong></div>
          </div>
          {data.products.length === 0 ? <EmptyState>No sales for this category with the current filters.</EmptyState> : (
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Product</th><th className="num">Units</th><th className="num">Orders</th>
                  <th className="num">Avg price</th><th className="num">Revenue</th><th>Share</th></tr></thead>
                <tbody>
                  {data.products.map((p) => (
                    <tr key={p.product_id}>
                      <td><strong>{p.product_name}</strong> <span className="muted small">{p.product_id}</span></td>
                      <td className="num">{formatNumber(p.units)}</td>
                      <td className="num">{formatNumber(p.orders)}</td>
                      <td className="num">{formatMoney(p.avg_price, cur)}</td>
                      <td className="num">{formatMoney(p.revenue, cur)}</td>
                      <td><div className="bar-cell"><span style={{ width: `${data.revenue ? (100 * p.revenue) / data.revenue : 0}%` }} /></div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="modal-foot">
            <button className="btn primary" onClick={() => navigate(`/orders?category=${encodeURIComponent(category)}`)}>
              View {category} orders →
            </button>
          </div>
        </>
      )}
    </Modal>
  )
}

export function OrderDetailModal({ orderId, onClose }) {
  const currency = useSelector((s) => s.filters.currency)
  const { data, error, isFetching, refetch } = useGetOrderQuery({ id: orderId, currency: currency !== 'INR' ? currency : undefined })
  const cur = data?.currency?.code || currency
  return (
    <Modal title={`Order #${orderId}`} onClose={onClose}>
      {isFetching && !data && <Loader block />}
      {error && <ErrorState message={errorMessage(error)} onRetry={refetch} />}
      {data && (
        <>
          <dl className="detail-grid">
            <div><dt>Customer</dt><dd>{data.customer.name} <span className="muted small">{data.customer.id}</span></dd></div>
            <div><dt>Order date</dt><dd>{data.order_date || <span className="muted">missing</span>}</dd></div>
            <div><dt>Shipment</dt><dd>{data.shipment.shipment_id || <span className="muted">not shipped</span>}</dd></div>
            <div><dt>Delivery</dt><dd><StatusBadge status={data.shipment.status} />
              {data.shipment.delivery_days != null && <span className="muted small"> in {data.shipment.delivery_days} days</span>}</dd></div>
          </dl>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Product</th><th>Category</th><th className="num">Qty</th><th className="num">Unit price</th><th className="num">Total</th></tr></thead>
              <tbody>
                {data.items.map((it, i) => (
                  <tr key={i}>
                    <td>{it.product_name} <span className="muted small">{it.product_id}</span></td>
                    <td>{it.category}</td>
                    <td className="num">{it.qty}</td>
                    <td className="num">{formatMoney(it.unit_price, cur)}</td>
                    <td className="num">{formatMoney(it.line_total, cur)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot><tr><td colSpan={4}>Total order value</td><td className="num"><strong>{formatMoney(data.order_value, cur)}</strong></td></tr></tfoot>
            </table>
          </div>
        </>
      )}
    </Modal>
  )
}
