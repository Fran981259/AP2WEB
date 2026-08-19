import React, { useEffect, useState } from 'react'
import { api } from './api.js'

const TOKEN_KEY = 'ap2web_token'
const USER_KEY = 'ap2web_user'

export default function App() {
  const [token, setToken] = useState(localStorage.getItem(TOKEN_KEY))
  const [username, setUsername] = useState(localStorage.getItem(USER_KEY) || '')

  function handleLogin(tok, user) {
    localStorage.setItem(TOKEN_KEY, tok)
    localStorage.setItem(USER_KEY, user)
    setToken(tok)
    setUsername(user)
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUsername('')
  }

  if (!token) return <AuthScreen onLogin={handleLogin} />

  return <Dashboard username={username} token={token} onLogout={handleLogout} />
}

function AuthScreen({ onLogin }) {
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
      const { token, username: user } = await api.login(username, password)
      onLogin(token, user)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <h1>AP2WEB</h1>
        <p className="subtitle">Motor de previsão esportiva — Poisson</p>
        <form onSubmit={submit}>
          <input placeholder="Usuário" value={username}
                 onChange={e => setUsername(e.target.value)} autoFocus />
          <input type="password" placeholder="Senha" value={password}
                 onChange={e => setPassword(e.target.value)} />
          {error && <div className="error">{error}</div>}
          <button className="btn-primary" disabled={loading}>
            {loading ? '...' : mode === 'login' ? 'Entrar' : 'Criar conta'}
          </button>
        </form>
        <p className="toggle">
          {mode === 'login' ? 'Não tem conta?' : 'Já tem conta?'}
          <a onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
            {mode === 'login' ? ' Cadastrar' : ' Entrar'}
          </a>
        </p>
      </div>
    </div>
  )
}

function Dashboard({ username, token, onLogout }) {
  const [tab, setTab] = useState('confronto')
  const [leagues, setLeagues] = useState([])
  const [selLeague, setSelLeague] = useState(null)
  const [matches, setMatches] = useState([])
  const [prediction, setPrediction] = useState(null)
  const [runs, setRuns] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // estado da aba confronto
  const [cfLeague, setCfLeague] = useState('')
  const [cfTeams, setCfTeams] = useState([])
  const [cfHome, setCfHome] = useState('')
  const [cfAway, setCfAway] = useState('')

  async function refreshLeagues() {
    setLeagues(await api.leagues(token))
  }

  useEffect(() => { refreshLeagues().catch(e => setError(e.message)); loadRuns() }, [])

  async function loadRuns() {
    try { setRuns(await api.runs(token)) } catch {}
  }

  async function onCfLeagueChange(leagueId) {
    setCfLeague(leagueId)
    setCfTeams([])
    setCfHome('')
    setCfAway('')
    setPrediction(null)
    if (!leagueId) return
    setLoading(true)
    try {
      setCfTeams(await api.leagueTeams(leagueId, token))
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  async function onCfPredict(e) {
    e.preventDefault()
    if (!cfLeague || !cfHome || !cfAway || cfHome === cfAway) {
      setError('Escolha a liga e dois times diferentes')
      return
    }
    setLoading(true); setError('')
    try {
      setPrediction(await api.predictFixture(Number(cfLeague), Number(cfHome), Number(cfAway), token))
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  async function onCfDemand() {
    if (!cfLeague) { setError('Escolha a liga primeiro'); return }
    const league = leagues.find(l => l.id === Number(cfLeague))
    setLoading(true); setError('')
    try {
      const res = await api.scrapeLeague(league.code, token)
      await refreshLeagues()
      await onCfLeagueChange(cfLeague)
      loadRuns()
      alert(`Demanda da liga ${league.name} concluída: ${res.matches_saved} novas partidas salvas`)
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  async function selectLeague(id) {
    setSelLeague(id)
    setPrediction(null)
    const ms = await api.leagueMatches(id, token)
    setMatches(ms)
  }

  async function openPrediction(id) {
    setLoading(true)
    setError('')
    try {
      setPrediction(await api.prediction(id, token))
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  async function runScrapeToday() {
    setLoading(true); setError('')
    try {
      const res = await api.scrapeToday(token)
      await refreshLeagues()
      if (selLeague) selectLeague(selLeague)
      loadRuns()
      alert(`Scrape ok: ${res.matches_found} partidas encontradas, ${res.matches_saved} novas salvas`)
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  async function runScrapeLeague(code) {
    setLoading(true); setError('')
    try {
      const res = await api.scrapeLeague(code, token)
      await refreshLeagues()
      loadRuns()
      alert(`Liga ${code}: ${res.matches_found} encontradas, ${res.matches_saved} salvas`)
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  return (
    <div className="app">
      <header>
        <div className="brand">AP2WEB</div>
        <nav>
          <button className={tab === 'confronto' ? 'active' : ''} onClick={() => setTab('confronto')}>Confronto</button>
          <button className={tab === 'liga' ? 'active' : ''} onClick={() => setTab('liga')}>Ligas e Jogos</button>
          <button className={tab === 'scrape' ? 'active' : ''} onClick={() => setTab('scrape')}>Raspagem</button>
        </nav>
        <div className="user">
          <span>{username}</span>
          <a onClick={onLogout}>Sair</a>
        </div>
      </header>
      {error && <div className="error banner">{error}</div>}

      {tab === 'confronto' && (
        <main className="confronto-page">
          <section className="panel">
            <h3>Montar Confronto</h3>
            <div className="cf-form">
              <label>
                Liga
                <select value={cfLeague} onChange={e => onCfLeagueChange(e.target.value)}>
                  <option value="">— selecione —</option>
                  {leagues.map(l => (
                    <option key={l.id} value={l.id}>{l.name} ({l.matches} jogos)</option>
                  ))}
                </select>
              </label>
              <button className="btn-small btn-demand" onClick={onCfDemand} disabled={loading || !cfLeague} title="Raspar resultados desta liga">
                {loading ? 'Raspando...' : 'Demanda de dados'}
              </button>
            </div>

            {cfLeague && (
              <div className="cf-form">
                <label>
                  Time da casa
                  <select value={cfHome} onChange={e => setCfHome(e.target.value)}>
                    <option value="">— selecione —</option>
                    {cfTeams.map(t => (
                      <option key={t.id} value={t.id} disabled={t.id === Number(cfAway)}>
                        {t.name} {t.games_played > 0 ? `(${t.games_played} jogos)` : ''}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Time visitante
                  <select value={cfAway} onChange={e => setCfAway(e.target.value)}>
                    <option value="">— selecione —</option>
                    {cfTeams.map(t => (
                      <option key={t.id} value={t.id} disabled={t.id === Number(cfHome)}>
                        {t.name} {t.games_played > 0 ? `(${t.games_played} jogos)` : ''}
                      </option>
                    ))}
                  </select>
                </label>
                <button className="btn-primary" onClick={onCfPredict} disabled={loading || !cfHome || !cfAway}>
                  {loading ? 'Prevendo...' : 'Prever confronto'}
                </button>
              </div>
            )}

            {cfLeague && cfTeams.length === 0 && !loading && (
              <p className="muted small">Nenhum time nesta liga ainda. Use "Demanda de dados" para raspar os resultados.</p>
            )}
          </section>

          {prediction && <PredictionView p={prediction} />}
        </main>
      )}

      {tab === 'liga' && (
        <main>
          <aside>
            <h3>Ligas no banco</h3>
            {leagues.length === 0 && <p className="muted">Nenhuma liga. Rape uma liga ou os jogos de hoje.</p>}
            <ul className="league-list">
              {leagues.map(l => (
                <li key={l.id} className={selLeague === l.id ? 'active' : ''} onClick={() => selectLeague(l.id)}>
                  <span className="name">{l.name}</span>
                  <span className="meta">{l.matches} jogos · {l.scheduled} agendados</span>
                </li>
              ))}
            </ul>
          </aside>

          <section className="content">
            {!selLeague && <p className="muted">Selecione uma liga para ver os jogos.</p>}
            {selLeague && (
              <>
                <h3>Partidas</h3>
                <table className="matches">
                  <thead>
                    <tr><th>Data</th><th>Casa</th><th>Placar</th><th>Fora</th><th></th></tr>
                  </thead>
                  <tbody>
                    {matches.map(m => (
                      <tr key={m.id}>
                        <td>{m.match_date}{m.kickoff ? ` ${m.kickoff}` : ''}</td>
                        <td>{m.home}</td>
                        <td>{m.status === 'played' ? `${m.ft_home} - ${m.ft_away}` : '—'}</td>
                        <td>{m.away}</td>
                        <td>
                          <button className="btn-small" onClick={() => openPrediction(m.id)} disabled={loading}>
                            Prever
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}

            {prediction && <PredictionView p={prediction} />}
          </section>
        </main>
      )}

      {tab === 'scrape' && (
        <main className="scrape-page">
          <section className="panel">
            <h3>Raspagem — Soccerstats.com</h3>
            <button className="btn-primary" onClick={runScrapeToday} disabled={loading}>
              {loading ? 'Raspando...' : 'Raspar jogos de hoje (matches.asp)'}
            </button>
            <p className="muted small">Coleta todas as ligas disponíveis na página de jogos de hoje, com estatísticas por time (GF, GA, Over/Under).</p>
            <div className="league-codes">
              {['argentina3', 'brazil2', 'spain', 'england', 'germany', 'italy', 'france'].map(c => (
                <button key={c} className="chip" onClick={() => runScrapeLeague(c)} disabled={loading}>
                  Resultados {c}
                </button>
              ))}
            </div>
            <p className="muted small">"Resultados {code}" raspa o histórico FT/HT da liga via results.asp.</p>
          </section>

          <section className="panel">
            <h3>Últimas raspagens</h3>
            <table className="runs">
              <thead><tr><th>#</th><th>Fonte</th><th>Status</th><th>Encontradas</th><th>Salvas</th><th>Início</th></tr></thead>
              <tbody>
                {runs.map(r => (
                  <tr key={r.id}>
                    <td>{r.id}</td>
                    <td>{r.source}</td>
                    <td><span className={`badge ${r.status}`}>{r.status}</span></td>
                    <td>{r.matches_found}</td>
                    <td>{r.matches_saved}</td>
                    <td>{r.started_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </main>
      )}
    </div>
  )
}

function PredictionView({ p }) {
  const { match, lambdas, probs, top_scores, proposals } = p
  return (
    <div className="prediction">
      <h3>Previsão — {match.home} x {match.away}</h3>
      <p className="muted small">{match.league} · {match.date}{match.kickoff ? ` · ${match.kickoff}` : ''}</p>

      <div className="lambda-row">
        <div>λ casa: <b>{lambdas.home}</b></div>
        <div>λ fora: <b>{lambdas.away}</b></div>
        <div>gols esperados: <b>{(lambdas.home + lambdas.away).toFixed(2)}</b></div>
      </div>

      <div className="grid-3">
        <div className="card">
          <h4>1X2</h4>
          {['1', 'X', '2'].map(k => (
            <div className="row-odds" key={k}>
              <span>{k === '1' ? match.home : k === '2' ? match.away : 'Empate'}</span>
              <span className="pct">{(probs['1x2'][k] * 100).toFixed(1)}%</span>
              <span className="odd">@{probs['odds_1x2'][k]}</span>
            </div>
          ))}
        </div>
        <div className="card">
          <h4>Gols</h4>
          {[1.5, 2.5, 3.5, 4.5].map(l => {
            const ov = probs['over'][`over_${l}`]
            const un = probs['under'][`under_${l}`]
            return (
              <div className="row-odds" key={l}>
                <span>Over {l}</span>
                <span className="pct">{(ov * 100).toFixed(1)}%</span>
                <span className="odd">@{ov > 0 ? (1 / ov).toFixed(2) : '—'}</span>
                <span className="muted small">under {un > 0 ? (1 / un).toFixed(2) : '—'}</span>
              </div>
            )
          })}
          <div className="row-odds">
            <span>BTTS Sim</span>
            <span className="pct">{(probs['btts']['sim'] * 100).toFixed(1)}%</span>
            <span className="odd">@{probs['btts']['sim'] > 0 ? (1 / probs['btts']['sim']).toFixed(2) : '—'}</span>
          </div>
        </div>
        <div className="card">
          <h4>Placar exato (top)</h4>
          {top_scores.slice(0, 8).map(s => (
            <div className="row-odds" key={s.score}>
              <span>{s.score}</span>
              <span className="pct">{s.prob}%</span>
              <span className="odd">@{s.odd}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h4>Propostas</h4>
        <ul className="proposals">
          {proposals.map((pr, i) => (
            <li key={i}>
              <span className="badge tipo">{pr.tipo}</span> {pr.jogada}
              {pr.confianca > 0 && <span className="pct">{pr.confianca}%</span>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
