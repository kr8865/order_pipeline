// Page layout: sidebar on the left, top bar, and the current page (chosen by the URL).
import { useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { IconDashboard, IconOrders, IconSearch, IconUpload } from './components/icons'
import { setCurrency } from './features/filters/filtersSlice'
import { useGetCurrenciesQuery } from './services/api'
import Dashboard from './pages/Dashboard'
import Orders from './pages/Orders'
import DataUpload from './pages/DataUpload'

const MENU = [
  { to: '/', label: 'Dashboard', icon: IconDashboard },
  { to: '/orders', label: 'Orders', icon: IconOrders },
  { to: '/data', label: 'Data upload', icon: IconUpload },
]

function TopBar() {
  const navigate = useNavigate()
  const dispatch = useDispatch()
  const currency = useSelector((state) => state.filters.currency)
  const { data: currencies } = useGetCurrenciesQuery()
  const [search, setSearch] = useState('')

  // Searching opens the Orders page with the search text in the URL.
  function handleSearch(e) {
    e.preventDefault()
    navigate(`/orders?search=${encodeURIComponent(search)}`)
  }

  return (
    <header className="topbar">
      <form className="top-search" onSubmit={handleSearch}>
        <IconSearch width={18} height={18} />
        <input placeholder="Search orders, customers, products…" value={search} onChange={(e) => setSearch(e.target.value)} />
      </form>
      <div className="topbar-right">
        <select value={currency} onChange={(e) => dispatch(setCurrency(e.target.value))} aria-label="Currency">
          <option value="INR">₹ INR</option>
          {currencies?.filter((c) => c.code !== 'INR').map((c) => <option key={c.code} value={c.code}>{c.code}</option>)}
        </select>
        <span className="avatar">KA</span>
      </div>
    </header>
  )
}

export default function App() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <svg viewBox="0 0 32 32" width="30" height="30" aria-hidden><rect width="32" height="32" rx="9" fill="#2065d1" />
            <path d="M8 22V14M14 22V9M20 22v-6M26 22V11" stroke="white" strokeWidth="3" strokeLinecap="round" /></svg>
          <span>Order Analytics</span>
        </div>

        <div className="user-card">
          <span className="avatar">KA</span>
          <div><strong>Kratika Agrawal</strong><span className="muted tiny">Admin</span></div>
        </div>

        <nav>
          {MENU.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === '/'} className="nav-link">
              <Icon width={20} height={20} /> <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="main">
        <TopBar />
        <main className="content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/orders" element={<Orders />} />
            <Route path="/data" element={<DataUpload />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
