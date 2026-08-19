import React, { useEffect, useMemo, useState } from 'react'
import { api } from './api.js'

const TOKEN_KEY = 'ap2web_token'
const USER_KEY = 'ap2web_user'

const FLAGS = {
  Spain: '🇪🇸', England: '🏴󠁧󠁢󠁥󠁮󠁧󠁿', Germany: '🇩🇪', Italy: '🇮🇹', France: '🇫🇷',
  Portugal: '🇵🇹', Netherlands: '🇳🇱', Belgium: '🇧🇪', Argentina: '🇦🇷',
  Brazil: '🇧🇷', Australia: '🇦🇺', Belarus: '🇧🇾', USA: '🇺🇸', Mexico: '🇲🇽',
  Colombia: '🇨🇴', Chile: '🇨🇱', Uruguay: '🇺🇾', Peru: '🇵🇪', Ecuador: '🇪🇨',
  Paraguay: '🇵🇾', Bolivia: '🇧🇴', Venezuela: '🇻🇪', Japan: '🇯🇵', China: '🇨🇳',
  Turkey: '🇹🇷', Greece: '🇬🇷', Russia: '🇷🇺', Ukraine: '🇺🇦', Poland: '🇵🇱',
  Switzerland: '🇨🇭', Austria: '🇦🇹', Scotland: '🏴󠁧󠁢󠁳󠁣󠁴󠁿', Ireland: '🇮🇪',
  Denmark: '🇩🇰', Sweden: '🇸🇪', Norway: '🇳🇴', Finland: '🇫🇮', Canada: '🇨🇦',
  'South Korea': '🇰🇷', 'Saudi Arabia': '🇸🇦', Qatar: '🇶🇦', Egypt: '🇪🇬', Croatia: '🇭🇷',
  Serbia: '🇷🇸', Romania: '🇷🇴', Czech: '🇨🇿', Slovakia: '🇸🇰', Hungary: '🇭🇺',
}

function flag(country) {
  if (!country) return '🏆'
  return FLAGS[country] || FLAGS[country.split(' ')[0]] || '🏆'
}

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

  const [cfLeague, setCfLeague] = useState('')
  const [cfTeams, setCfTeams] = useState([])
  const [cfHome, setCfHome] = useState('')
  const [cfAway, setCfAway] = useState('')

  const [hist, setHist] = useState(null)
  const [leagueSearch, setLeagueSearch] = useState('')

  async function refreshLeagues() {
    setLeagues(await api.leagues(token))
  }

  useEffect(() => {
    refreshLeagues().catch(e => setError(e.message))
    loadRuns()
    if (tab === 'historico') loadHistory()
  }, [tab])

  async function loadRuns() {
    try { setRuns(await api.runs(token)) } catch {}
  }

  async function loadHistory() {
    try { setHist(await api.predictions(token)) } catch (e) { setError(e.message) }
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
    try {
      setMatches(await api.leagueMatches(id, token))
    } catch (e) { setError(e.message) }
  }

  async function openPrediction(id) {
    setLoading(true); setError('')
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

  async function onSavePrediction(p) {
    try {
      await api.savePrediction(p, token)
      alert('Previsão salva no histórico')
      loadHistory()
    } catch (e) { setError(e.message) }
  }

  async function onDeletePrediction(id) {
    try {
      await api.deletePrediction(id, token)
      loadHistory()
    } catch (e) { setError(e.message) }
  }

  const filteredLeagues = useMemo(() => {
    const q = leagueSearch.trim().toLowerCase()
    if (!q) return leagues
    return leagues.filter(l =>
      l.name.toLowerCase().includes(q) || (l.country || '').toLowerCase().includes(q))
  }, [leagues, leagueSearch])

  const selLeagueObj = selLeague ? leagues.find(l => l.id === selLeague) : null

  return (
    <div className="app">
      <header>
        <div className="brand">⚽ AP2WEB</div>
        <nav>
          <button className={tab === 'confronto' ? 'active' : ''} onClick={() => setTab('confronto')}>Confronto</button>
          <button className={tab === 'liga' ? 'active' : ''} onClick={() => setTab('liga')}>Ligas</button>
          <button className={tab === 'historico' ? 'active' : ''} onClick={() => setTab('historico')}>Histórico</button>
          <button className={tab === 'scrape' ? 'active' : ''} onClick={() => setTab('scrape')}>Raspagem</button>
        </nav>
        <div className="user">
          <span>{username}</span>
          <a onClick={onLogout}>Sair</a>
        </div>
      </header>
      {error && <div className="error banner" onClick={() => setError('')}>✕ {error}</div>}

      {tab === 'confronto' && (
        <main className="column">
          <section className="panel">
            <h3>Montar Confronto</h3>
            <div className="cf-form">
              <label>
                Liga
                <select value={cfLeague} onChange={e => onCfLeagueChange(e.target.value)}>
                  <option value="">— selecione —</option>
                  {leagues.map(l => (
                    <option key={l.id} value={l.id}>
                      {flag(l.country)} {l.name} ({l.matches} jogos)
                    </option>
                  ))}
                </select>
              </label>
              <button className="btn-small btn-demand" onClick={onCfDemand} disabled={loading || !cfLeague} title="Raspar resultados desta liga">
                {loading ? 'Raspando...' : '📥 Demanda de dados'}
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
                  {loading ? 'Prevendo...' : '🔮 Prever confronto'}
                </button>
              </div>
            )}

            {cfLeague && cfTeams.length === 0 && !loading && (
              <p className="muted small">Nenhum time nesta liga ainda. Use "Demanda de dados" para raspar os resultados.</p>
            )}
          </section>

          {prediction && (
            <PredictionView p={prediction} token={token} onSave={onSavePrediction} />
          )}
        </main>
      )}

      {tab === 'liga' && (
        <main>
          <aside>
            <h3>Ligas no banco</h3>
            <input className="search" placeholder="🔎 Buscar liga ou país..."
                   value={leagueSearch} onChange={e => setLeagueSearch(e.target.value)} />
            {filteredLeagues.length === 0 && <p className="muted">Nenhuma liga. Rape uma liga ou os jogos de hoje.</p>}
            <ul className="league-list">
              {filteredLeagues.map(l => (
                <li key={l.id} className={selLeague === l.id ? 'active' : ''} onClick={() => selectLeague(l.id)}>
                  <span className="name">{flag(l.country)} {l.name}</span>
                  <span className="meta">{l.matches} jogos · {l.scheduled} agendados</span>
                </li>
              ))}
            </ul>
          </aside>

          <section className="content">
            {!selLeague && <p className="muted">Selecione uma liga para ver os jogos.</p>}
            {selLeague && selLeagueObj && (
              <>
                <h3>{flag(selLeagueObj.country)} {selLeagueObj.name} — Partidas</h3>
                <div className="table-scroll">
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
                </div>
              </>
            )}

            {prediction && (
              <PredictionView p={prediction} token={token} onSave={onSavePrediction} />
            )}
          </section>
        </main>
      )}

      {tab === 'historico' && (
        <main className="column">
          <section className="panel">
            <h3>📊 Desempenho</h3>
            {hist && (
              <div className="hist-stats">
                <Stat label="Total" value={hist.stats.total} />
                <Stat label="Acertos" value={hist.stats.correct} ok />
                <Stat label="Erros" value={hist.stats.wrong} bad />
                <Stat label="Pendentes" value={hist.stats.pending} />
                <Stat label="Aproveitamento" value={`${hist.stats.hit_rate}%`} ok />
              </div>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <h3>Minhas previsões</h3>
              <button className="btn-small" onClick={loadHistory}>Atualizar</button>
            </div>
            {hist && hist.items.length === 0 && <p className="muted">Nenhuma previsão salva ainda.</p>}
            <div className="table-scroll">
              <table className="runs hist">
                <thead>
                  <tr><th>Status</th><th>Jogo</th><th>Jogada</th><th>Prob.</th><th>Odd</th><th>Data</th><th></th></tr>
                </thead>
                <tbody>
                  {(hist?.items || []).map(h => (
                    <tr key={h.id}>
                      <td><span className={`badge ${h.status}`}>{h.status}</span></td>
                      <td><b>{h.home_name}</b> x <b>{h.away_name}</b></td>
                      <td>{h.pick_label}</td>
                      <td>{h.prob}%</td>
                      <td>@{h.odd}</td>
                      <td>{h.created_at}</td>
                      <td><button className="btn-small" onClick={() => onDeletePrediction(h.id)}>✕</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </main>
      )}

      {tab === 'scrape' && (
        <main className="column">
          <section className="panel">
            <h3>Raspagem — Soccerstats.com</h3>
            <div className="btn-row">
              <button className="btn-primary" onClick={runScrapeToday} disabled={loading}>
                {loading ? 'Raspando...' : '📥 Raspar jogos de hoje'}
              </button>
              <span className="muted small">Coleta todas as ligas da página de jogos de hoje, com estatísticas por time.</span>
            </div>
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
            <div className="table-scroll">
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
            </div>
          </section>
        </main>
      )}
    </div>
  )
}

function Stat({ label, value, ok, bad }) {
  return (
    <div className={`stat ${ok ? 'ok' : ''} ${bad ? 'bad' : ''}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

function PredictionView({ p, token, onSave }) {
  const { match, lambdas, probs, top_scores, proposals, compare } = p
  const [picked, setPicked] = useState(null)

  const pickOptions = useMemo(() => {
    const opts = []
    const p1 = probs['1x2']
    const fav = Object.keys(p1).reduce((a, b) => p1[a] >= p1[b] ? a : b)
    const favName = fav === '1' ? match.home : fav === '2' ? match.away : 'Empate'
    opts.push({ type: '1X2', value: fav, label: `1X2: ${favName}`, prob: Math.round(p1[fav] * 1000) / 10 })
    for (const line of [1.5, 2.5]) {
      const ov = probs['over'][`over_${line}`]
      const un = probs['under'][`under_${line}`]
      if (ov >= un) opts.push({ type: 'GOLS', value: `over_${line}`, label: `Over ${line}`, prob: Math.round(ov * 1000) / 10 })
      else opts.push({ type: 'GOLS', value: `under_${line}`, label: `Under ${line}`, prob: Math.round(un * 1000) / 10 })
    }
    const btts = probs['btts']
    if (btts['sim'] >= 0.5) opts.push({ type: 'BTTS', value: 'sim', label: 'BTTS Sim', prob: Math.round(btts['sim'] * 1000) / 10 })
    else opts.push({ type: 'BTTS', value: 'nao', label: 'BTTS Não', prob: Math.round(btts['nao'] * 1000) / 10 })
    if (top_scores[0]) opts.push({ type: 'PLACAR', value: top_scores[0].score, label: `Placar ${top_scores[0].score}`, prob: top_scores[0].prob })
    return opts
  }, [probs, top_scores, match])

  useEffect(() => { setPicked(null) }, [p])

  function save() {
    if (!picked) { alert('Escolha uma jogada para salvar'); return }
    const odd = picked.prob > 0 ? (100 / picked.prob).toFixed(2) : '—'
    onSave({
      league_id: match.league_id || null,
      match_id: match.id || null,
      home_team_id: match.home_id || null,
      away_team_id: match.away_id || null,
      home_name: match.home,
      away_name: match.away,
      match_date: match.date || null,
      pick_type: picked.type,
      pick_value: picked.value,
      pick_label: picked.label,
      prob: picked.prob,
      odd,
      payload: { lambdas, probs, top_scores },
    })
  }

  return (
    <div className="prediction">
      <div className="pred-head">
        <div>
          <h3>{match.home} <span className="vs">x</span> {match.away}</h3>
          <p className="muted small">{match.league} · {match.date}{match.kickoff ? ` · ${match.kickoff}` : ''}</p>
        </div>
        <div className="lambda-chip" title="Gols esperados do modelo Poisson">
          <b>{lambdas.home}</b> · <b>{lambdas.away}</b>
        </div>
      </div>

      {compare && compare.h2h?.length > 0 && (
        <div className="card h2h">
          <h4>⚔️ Confrontos diretos</h4>
          <div className="h2h-row">
            {compare.h2h.slice(0, 5).map((m, i) => (
              <div className="h2h-item" key={i}>
                <span className="h2h-date">{m.match_date}</span>
                <span>{m.home} <b>{m.ft_home}–{m.ft_away}</b> {m.away}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid-3">
        <Card title="1X2">
          {['1', 'X', '2'].map(k => {
            const v = probs['1x2'][k]
            return (
              <div className="bar-row" key={k}>
                <div className="bar-label">{k === '1' ? match.home : k === '2' ? match.away : 'Empate'}</div>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${v * 100}%` }} />
                </div>
                <div className="bar-val">{(v * 100).toFixed(1)}% <span className="odd">@{probs['odds_1x2'][k]}</span></div>
              </div>
            )
          })}
        </Card>
        <Card title="Gols">
          {[1.5, 2.5, 3.5, 4.5].map(l => {
            const ov = probs['over'][`over_${l}`]
            const un = probs['under'][`under_${l}`]
            return (
              <div className="bar-row" key={l}>
                <div className="bar-label">Over {l}</div>
                <div className="bar-track">
                  <div className="bar-fill over" style={{ width: `${ov * 100}%` }} />
                </div>
                <div className="bar-val">{(ov * 100).toFixed(1)}% <span className="odd">@{ov > 0 ? (1 / ov).toFixed(2) : '—'}</span>
                  <span className="muted small">U{un > 0 ? (1 / un).toFixed(2) : '—'}</span></div>
              </div>
            )
          })}
          <div className="bar-row">
            <div className="bar-label">BTTS Sim</div>
            <div className="bar-track">
              <div className="bar-fill btts" style={{ width: `${probs['btts']['sim'] * 100}%` }} />
            </div>
            <div className="bar-val">{(probs['btts']['sim'] * 100).toFixed(1)}%
              <span className="odd">@{probs['btts']['sim'] > 0 ? (1 / probs['btts']['sim']).toFixed(2) : '—'}</span></div>
          </div>
        </Card>
        <Card title="Heatmap Poisson">
          <Heatmap probs={probs} lambdas={lambdas} />
        </Card>
      </div>

      <div className="grid-3">
        <Card title="Placar exato (top)">
          {top_scores.slice(0, 8).map(s => (
            <div className="row-odds" key={s.score}>
              <span>{s.score}</span>
              <span className="pct">{s.prob}%</span>
              <span className="odd">@{s.odd}</span>
            </div>
          ))}
        </Card>
        <Card title="Propostas">
          <ul className="proposals">
            {proposals.map((pr, i) => (
              <li key={i}>
                <span className={`badge tipo ${pr.tipo.toLowerCase()}`}>{pr.tipo}</span> {pr.jogada}
                {pr.confianca > 0 && <span className="pct">{pr.confianca}%</span>}
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Salvar no histórico">
          <p className="muted small">Escolha a jogada e registre para acompanhar acertos/erros.</p>
          <select className="pick-select" value={picked ? JSON.stringify({ t: picked.type, v: picked.value }) : ''}
                  onChange={e => {
                    const sel = pickOptions.find(o => JSON.stringify({ t: o.type, v: o.value }) === e.target.value)
                    setPicked(sel)
                  }}>
            <option value="">— escolha —</option>
            {pickOptions.map((o, i) => (
              <option key={i} value={JSON.stringify({ t: o.type, v: o.value })}>
                {o.label} ({o.prob}%)
              </option>
            ))}
          </select>
          <button className="btn-primary btn-block" onClick={save} disabled={!picked}>
            💾 Salvar previsão
          </button>
        </Card>
      </div>
    </div>
  )
}

function Card({ title, children }) {
  return (
    <div className="card">
      <h4>{title}</h4>
      {children}
    </div>
  )
}

function Heatmap({ probs, lambdas }) {
  const scores = probs['scores']
  const cells = []
  for (let i = 0; i <= 4; i++) {
    for (let j = 0; j <= 4; j++) {
      const p = scores[`${i}-${j}`] || 0
      cells.push({ i, j, p })
    }
  }
  const max = Math.max(...cells.map(c => c.p), 0.0001)
  return (
    <div>
      <div className="heat-legend">
        <span>{lambdas.home.toFixed(2)} casa →</span>
        <span className="muted">linha = gols casa · coluna = gols fora</span>
      </div>
      <div className="heatmap">
        <div className="heat-corner" />
        {[0, 1, 2, 3, 4].map(j => <div className="heat-col-label" key={j}>{j}</div>)}
        {[0, 1, 2, 3, 4].map(i => (
          <React.Fragment key={i}>
            <div className="heat-row-label">{i}</div>
            {[0, 1, 2, 3, 4].map(j => {
              const p = scores[`${i}-${j}`] || 0
              const alpha = p / max
              return (
                <div className="heat-cell" key={j}
                     style={{ background: `rgba(79,124,255,${(alpha * 0.95).toFixed(2)})` }}
                     title={`${i}-${j}: ${(p * 100).toFixed(1)}%`}>
                  {(p * 100).toFixed(0)}
                </div>
              )
            })}
          </React.Fragment>
        ))}
      </div>
    </div>
  )
}