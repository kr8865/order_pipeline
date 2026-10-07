import { configureStore } from '@reduxjs/toolkit'
import { setupListeners } from '@reduxjs/toolkit/query'
import { api } from '../services/api'
import filtersReducer, { persistFilters } from '../features/filters/filtersSlice'

export const store = configureStore({
  reducer: {
    filters: filtersReducer,
    [api.reducerPath]: api.reducer,
  },
  middleware: (getDefault) => getDefault().concat(api.middleware),
})

setupListeners(store.dispatch) // refetch on window focus / reconnect
persistFilters(store)
