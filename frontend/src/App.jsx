import { useEffect, useState } from 'react'
import { api, setOnUnauthorized } from './api.js'
import AuthScreen from './features/auth/AuthScreen.jsx'
import Dashboard from './features/dashboard/Dashboard.jsx'

export default function App() {
  const [username, setUsername] = useState(null)
  const [role, setRole] = useState('user')
  const [restoring, setRestoring] = useState(true)

  useEffect(() => {
    let active = true
    api.me()
      .then((data) => { if (active) { setUsername(data.username); setRole(data.role || 'user') } })
      .catch(() => {})
      .finally(() => { if (active) setRestoring(false) })
    setOnUnauthorized(() => { if (active) { setUsername(null); setRestoring(false) } })
    return () => { active = false; setOnUnauthorized(null) }
  }, [])

  function handleLogin(data) {
    setUsername(data.username)
    setRole(data.role || 'user')
  }

  function handleLogout() {
    api.logout().catch(() => {})
    setUsername(null)
    setRole('user')
  }

  if (restoring) {
    return (
      <div className="auth-wrap">
        <div className="auth-card"><p className="muted">Carregando sessão…</p></div>
      </div>
    )
  }
  if (!username) return <AuthScreen onLogin={handleLogin} />

  return <Dashboard username={username} role={role} token={null} onLogout={handleLogout} />
}
