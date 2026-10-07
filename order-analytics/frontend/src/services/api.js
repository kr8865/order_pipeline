import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'

const BASE_URL = import.meta.env.VITE_API_URL || '/api'

/** Turn the backend's {error: {message}} envelope (or a network failure) into a readable string. */
export function errorMessage(err) {
  if (!err) return null
  if (err.status === 'FETCH_ERROR') return 'Cannot reach the API server. Is the backend running on port 8000?'
  if (err.status === 'PARSING_ERROR') return 'The server returned an unexpected response.'
  const msg = err.data?.error?.message
  const details = err.data?.error?.details
  if (details?.length) return `${msg}: ${details.map((d) => `${d.field} – ${d.message}`).join('; ')}`
  return msg || err.error || `Request failed (${err.status})`
}

/** Build query params from the global filter state, dropping empty values. */
export function filterParams(f, extra = {}) {
  const p = {
    start_date: f.startDate || undefined,
    end_date: f.endDate || undefined,
    category: f.categories?.length ? f.categories.join(',') : undefined,
    status: f.statuses?.length ? f.statuses.join(',') : undefined,
    currency: f.currency && f.currency !== 'INR' ? f.currency : undefined,
    ...extra,
  }
  return Object.fromEntries(Object.entries(p).filter(([, v]) => v !== undefined && v !== ''))
}

export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({ baseUrl: BASE_URL, timeout: 20000 }),
  tagTypes: ['Data'],
  keepUnusedDataFor: 60,
  // Data can also be ingested outside this app (Swagger, Postman, scripts/seed.py), so don't
  // trust the client cache: refetch when a page opens, when the tab regains focus, and on reconnect.
  refetchOnMountOrArgChange: true,
  refetchOnFocus: true,
  refetchOnReconnect: true,
  endpoints: (b) => ({
    getSummary: b.query({ query: (params) => ({ url: '/analytics/summary', params }), providesTags: ['Data'] }),
    getFilters: b.query({ query: () => '/analytics/filters', providesTags: ['Data'] }),
    getCategory: b.query({
      query: ({ category, ...params }) => ({ url: `/analytics/category/${encodeURIComponent(category)}`, params }),
      providesTags: ['Data'],
    }),
    getOrders: b.query({ query: (params) => ({ url: '/orders', params }), providesTags: ['Data'] }),
    getOrder: b.query({
      query: ({ id, currency }) => ({ url: `/orders/${encodeURIComponent(id)}`, params: currency ? { currency } : {} }),
      providesTags: ['Data'],
    }),
    getDataQuality: b.query({ query: () => '/analytics/data-quality', providesTags: ['Data'] }),
    getCurrencies: b.query({ query: () => '/currency/list', keepUnusedDataFor: 3600 }),
    uploadFile: b.mutation({
      query: ({ kind, file }) => {
        const body = new FormData()
        body.append('file', file)
        return { url: `/ingest/${kind}`, method: 'POST', body }
      },
      invalidatesTags: ['Data'], // every dashboard query refetches after new data arrives
    }),
    loadSample: b.mutation({
      query: (dataset = 'sample') => ({ url: '/ingest/sample', method: 'POST', params: { dataset } }),
      invalidatesTags: ['Data'],
    }),
  }),
})

export const {
  useGetSummaryQuery, useGetFiltersQuery, useGetCategoryQuery, useGetOrdersQuery, useGetOrderQuery,
  useGetCurrenciesQuery, useGetDataQualityQuery, useUploadFileMutation, useLoadSampleMutation,
} = api
