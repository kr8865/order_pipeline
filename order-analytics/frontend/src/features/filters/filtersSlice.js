import { createSlice } from '@reduxjs/toolkit'

const STORAGE_KEY = 'order-analytics:prefs'
// Only display preferences are remembered between visits. Date/category/status filters are NOT,
// so a filter from an old dataset can never hide newly loaded data.
const PERSISTED = ['currency', 'metric', 'granularity']

const defaults = {
  startDate: '',
  endDate: '',
  categories: [],
  statuses: [],
  currency: 'INR',
  metric: 'both', // 'both' | 'revenue' | 'orders'  -> Revenue vs Orders toggle
  granularity: 'auto',
}

function loadInitial() {
  try {
    localStorage.removeItem('order-analytics:filters') // old key that also stored filters
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null') || {}
    const prefs = Object.fromEntries(PERSISTED.filter((k) => k in saved).map((k) => [k, saved[k]]))
    return { ...defaults, ...prefs }
  } catch {
    return defaults
  }
}

const toggleIn = (list, value) => (list.includes(value) ? list.filter((v) => v !== value) : [...list, value])

const filtersSlice = createSlice({
  name: 'filters',
  initialState: loadInitial(),
  reducers: {
    setDateRange(state, { payload }) {
      state.startDate = payload.startDate ?? state.startDate
      state.endDate = payload.endDate ?? state.endDate
    },
    toggleCategory(state, { payload }) { state.categories = toggleIn(state.categories, payload) },
    setCategories(state, { payload }) { state.categories = payload },
    toggleStatus(state, { payload }) { state.statuses = toggleIn(state.statuses, payload) },
    setStatuses(state, { payload }) { state.statuses = payload },
    setCurrency(state, { payload }) { state.currency = payload },
    setMetric(state, { payload }) { state.metric = payload },
    setGranularity(state, { payload }) { state.granularity = payload },
    resetFilters(state) {
      return { ...defaults, currency: state.currency, metric: state.metric }
    },
  },
})

export const {
  setDateRange, toggleCategory, setCategories, toggleStatus, setStatuses, setCurrency, setMetric,
  setGranularity, resetFilters,
} = filtersSlice.actions

export const selectFilters = (s) => s.filters
export const activeFilterCount = (f) =>
  (f.startDate ? 1 : 0) + (f.endDate ? 1 : 0) + f.categories.length + f.statuses.length

export function persistFilters(store) {
  let last
  store.subscribe(() => {
    const f = store.getState().filters
    if (f !== last) {
      last = f
      const prefs = Object.fromEntries(PERSISTED.map((k) => [k, f[k]]))
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs)) } catch { /* storage unavailable */ }
    }
  })
}

export default filtersSlice.reducer
