import { useState } from 'react'
import { api } from '../../api.js'

export default function AuthScreen({ onLogin }) {
  const [mode, setMode] = useState('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'register') await api.register(username, password)
      const data = await api.login(username, password)
      onLogin(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-logo">⚽</div>
        <h1>AP2WEB</h1>
        <p className="subtitle">Motor de previsão esportiva — Poisson</p>
        <form onSubmit={submit}>
          <input placeholder="Usuário" value={username}
                 onChange={e => setUsername(e.target.value)} autoFocus />
          <input type="password" placeholder="Senha" value={password}
                 onChange={e => setPassword(e.target.value)} />
          {error && <div className="error">{error}</div>}
          <button className="btn-primary btn-block" disabled={loading}>
            {loading ? 'Aguarde...' : mode === 'login' ? 'Entrar' : 'Criar conta'}
          </button>
        </form>
        <p className="toggle">
          {mode === 'login' ? 'Não tem conta?' : 'Já tem conta?'}
          <button type="button" className="btn-link" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
            {mode === 'login' ? ' Cadastrar' : ' Entrar'}
          </button>
        </p>
      </div>
    </div>
  )
}
