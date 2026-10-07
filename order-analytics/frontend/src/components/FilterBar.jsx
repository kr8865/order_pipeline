// One row of filters: date range, category and delivery status.
// The values live in Redux (filtersSlice), so every chart and table uses the same filters.
import { useDispatch, useSelector } from 'react-redux'
import { useGetFiltersQuery } from '../services/api'
import {
  activeFilterCount, resetFilters, selectFilters, setCategories, setDateRange, setStatuses,
} from '../features/filters/filtersSlice'

export default function FilterBar() {
  const dispatch = useDispatch()
  const filters = useSelector(selectFilters)
  const { data: options } = useGetFiltersQuery() // available categories, statuses and date range

  const wrongRange = filters.startDate && filters.endDate && filters.startDate > filters.endDate

  return (
    <div className="filter-bar card">
      <label className="filter">
        <span>From</span>
        <input type="date" value={filters.startDate} min={options?.min_date} max={options?.max_date}
          onChange={(e) => dispatch(setDateRange({ startDate: e.target.value }))} />
      </label>

      <label className="filter">
        <span>To</span>
        <input type="date" value={filters.endDate} min={options?.min_date} max={options?.max_date}
          onChange={(e) => dispatch(setDateRange({ endDate: e.target.value }))} />
      </label>

      <label className="filter">
        <span>Category</span>
        <select value={filters.categories[0] ?? ''}
          onChange={(e) => dispatch(setCategories(e.target.value ? [e.target.value] : []))}>
          <option value="">All categories</option>
          {options?.categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </label>

      <label className="filter">
        <span>Delivery status</span>
        <select value={filters.statuses[0] ?? ''}
          onChange={(e) => dispatch(setStatuses(e.target.value ? [e.target.value] : []))}>
          <option value="">All statuses</option>
          {options?.statuses.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>

      <button className="btn" disabled={activeFilterCount(filters) === 0} onClick={() => dispatch(resetFilters())}>
        Clear filters
      </button>

      {wrongRange && <p className="field-error">"From" date is after "To" date</p>}
      {options?.min_date && <p className="muted tiny filter-note">Data from {options.min_date} to {options.max_date}</p>}
    </div>
  )
}
