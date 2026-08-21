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

const CONTINENTS = {
  Brazil: 'América do Sul', Argentina: 'América do Sul', Chile: 'América do Sul',
  Uruguay: 'América do Sul', Peru: 'América do Sul', Ecuador: 'América do Sul',
  Paraguay: 'América do Sul', Bolivia: 'América do Sul', Venezuela: 'América do Sul',
  Colombia: 'América do Sul',
  USA: 'América do Norte', Mexico: 'América do Norte', Canada: 'América do Norte',
  Spain: 'Europa', England: 'Europa', Germany: 'Europa', Italy: 'Europa',
  France: 'Europa', Portugal: 'Europa', Netherlands: 'Europa', Belgium: 'Europa',
  Turkey: 'Europa', Greece: 'Europa', Russia: 'Europa', Ukraine: 'Europa',
  Poland: 'Europa', Switzerland: 'Europa', Austria: 'Europa', Scotland: 'Europa',
  Ireland: 'Europa', Denmark: 'Europa', Sweden: 'Europa', Norway: 'Europa',
  Finland: 'Europa', Croatia: 'Europa', Serbia: 'Europa', Romania: 'Europa',
  Czech: 'Europa', Slovakia: 'Europa', Hungary: 'Europa', Belarus: 'Europa',
  Japan: 'Ásia', China: 'Ásia', 'South Korea': 'Ásia', 'Saudi Arabia': 'Ásia',
  Qatar: 'Ásia',
  Egypt: 'África',
  Australia: 'Oceania',
}

const CONTINENT_ORDER = ['Europa', 'América do Sul', 'América do Norte', 'Ásia', 'África', 'Oceania', 'Outros']

function continent(country) {
  if (!country) return 'Outros'
  return CONTINENTS[country] || CONTINENTS[country.split(' ')[0]] || 'Outros'
}

const STAT_LABELS = {
  xg: 'xG', xg_on_target: 'xG no alvo', possession: 'Posse',
  shots_total: 'Chutes', shots_on_target: 'No gol', shots_off_target: 'Fora',
  shots_inside_box: 'Na área', shots_outside_box: 'Fora área', blocked_shots: 'Bloqueados',
  big_chances: 'Grandes chances', big_chances_missed: 'Chances perdidas',
  corners: 'Escanteios', fouls: 'Faltas', yellow_cards: 'Amarelos', red_cards: 'Vermelhos',
  passes: 'Passes', accurate_passes: 'Passes certos', offsides: 'Impedimentos',
  saves: 'Defesas', interceptions: 'Interceptações', recoveries: 'Recuperações',
  tackles: 'Desarmes', dribbles: 'Dribles', duels: 'Duelos', aerial_duels: 'Duelos aéreos',
  final_third: 'Final 1/3', throw_ins: 'Laterais', goal_kicks: 'Tiros de meta',
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
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [cfLeague, setCfLeague] = useState('')
  const [cfTeams, setCfTeams] = useState([])
  const [cfHome, setCfHome] = useState('')
  const [cfAway, setCfAway] = useState('')

  const [hist, setHist] = useState(null)
  const [leagueSearch, setLeagueSearch] = useState('')
  const [openConts, setOpenConts] = useState(() => new Set(['Europa']))
  const [learn, setLearn] = useState(null)
  const [cal, setCal] = useState(null)
  const [calTimer, setCalTimer] = useState(null)
  const [backtest, setBacktest] = useState(null)
  const [backtesting, setBacktesting] = useState(false)
  const [curve, setCurve] = useState(null)
  const [curveLoading, setCurveLoading] = useState(false)

  const [sofa, setSofa] = useState(null)
  const [sofaTimer, setSofaTimer] = useState(null)
  const [sofaStatus, setSofaStatus] = useState(null)
  const [sofaLeague, setSofaLeague] = useState('')
  const [sofaSelFields, setSofaSelFields] = useState(['xg', 'possession', 'shots_on_target', 'corners', 'yellow_cards'])
  const [sofaTeamFilter, setSofaTeamFilter] = useState('')
  const [sofaRoundFilter, setSofaRoundFilter] = useState('')

  async function refreshLeagues() {
    const raw = await api.leagues(token)
    // Deduplicate by league id — sem spread de iterador (bug de transpilação esbuild)
    const byId = {}
    raw.forEach(l => { byId[l.id] = l })
    setLeagues(Object.values(byId))
  }

  useEffect(() => {
    refreshLeagues().catch(e => setError(e.message))
    if (tab === 'historico') loadHistory()
    if (tab === 'aprendizado') loadLearning()
    if (tab === 'sofascore') loadSofa()
  }, [tab])

  useEffect(() => () => clearInterval(calTimer), [calTimer])
  useEffect(() => () => clearInterval(sofaTimer), [sofaTimer])

  async function loadHistory() {
    try { setHist(await api.predictions(token)) } catch (e) { setError(e.message) }
  }

  async function loadLearning() {
    try { setLearn(await api.learningStatus(token)) } catch (e) { setError(e.message) }
  }

  async function loadSofa(leagueId) {
    try { setSofa(await api.sofascoreData(leagueId, token)) } catch (e) { setError(e.message) }
  }

  async function startSofaSync(leagueId) {
    setLoading(true); setError('')
    try {
      if (leagueId) await api.sofascoreSyncLeague(leagueId, token)
      else await api.sofascoreSync(token)
      const t = setInterval(async () => {
        try {
          const s = await api.sofascoreStatus(token)
          setSofaStatus(s)
          if (!s.running) {
            clearInterval(t); setSofaTimer(null)
            loadSofa(sofaLeague || undefined)
            // refreshLeagues removed from here - called only once on login/tab change
          }
        } catch {}
      }, 2500)
      setSofaTimer(t)
      setSofaStatus({ running: true, done: 0, total: 1, current: 'aguardando...' })
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  async function startCalibration() {
    setLoading(true); setError('')
    try {
      await api.learningCalibrate(token)
      clearInterval(calTimer)
      const t = setInterval(async () => {
        try {
          const s = await api.learningCalibrateStatus(token)
          setCal(s)
          if (!s.running) {
            clearInterval(t); setCalTimer(null)
            loadLearning()
          }
        } catch {}
      }, 3000)
      setCalTimer(t)
      loadLearning()
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  async function runBacktest(leagueId) {
    setBacktesting(true); setBacktest(null); setError('')
    try {
      setBacktest(await api.learningBacktest(leagueId, token))
    } catch (e) { setError(e.message) }
    setBacktesting(false)
  }

  async function loadCurve() {
    setCurveLoading(true); setError('')
    try {
      setCurve(await api.learningCurve(token))
    } catch (e) { setError(e.message) }
    setCurveLoading(false)
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
    setLoading(true); setError('')
    try {
      const res = await api.sofascoreSyncLeague(cfLeague, token)
      await refreshLeagues()
      await onCfLeagueChange(cfLeague)
      if (res.ok) alert(`Sincronização da liga concluída: ${res.matches_saved} novas partidas salvas`)
      else alert(`Falha na sincronização: ${res.error || 'erro desconhecido'}`)
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

  const groupedByContinent = useMemo(() => {
    const groups = {}
    for (const l of filteredLeagues) {
      const key = continent(l.country)
      if (!groups[key]) groups[key] = []
      groups[key].push(l)
    }
    return Object.entries(groups).sort((a, b) => {
      const ia = CONTINENT_ORDER.indexOf(a[0])
      const ib = CONTINENT_ORDER.indexOf(b[0])
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
    })
  }, [filteredLeagues])

  const selLeagueObj = selLeague ? leagues.find(l => l.id === selLeague) : null

  function toggleCont(c) {
    setOpenConts(prev => {
      const next = new Set(prev)
      if (next.has(c)) next.delete(c)
      else next.add(c)
      return next
    })
  }

  return (
    <div className="app">
      <header>
        <div className="brand">⚽ AP2WEB</div>
        <nav>
          <button className={tab === 'confronto' ? 'active' : ''} onClick={() => setTab('confronto')}>Confronto</button>
          <button className={tab === 'historico' ? 'active' : ''} onClick={() => setTab('historico')}>Histórico</button>
          <button className={tab === 'aprendizado' ? 'active' : ''} onClick={() => setTab('aprendizado')}>Aprendizado</button>
          <button className={tab === 'dados' ? 'active' : ''} onClick={() => setTab('dados')}>Dados</button>
          <button className={tab === 'sofascore' ? 'active' : ''} onClick={() => setTab('sofascore')}>Sofascore</button>
        </nav>
        <div className="user">
          <span>{username}</span>
          <a onClick={onLogout}>Sair</a>
        </div>
      </header>
      {error && <div className="error banner" onClick={() => setError('')}>✕ {error}</div>}

      {tab === 'confronto' && (
        <main>
          <aside>
            <h3>Ligas no banco <span className="muted small">({leagues.length})</span></h3>
            <input className="search" placeholder="🔎 Buscar liga ou país..."
                   value={leagueSearch} onChange={e => setLeagueSearch(e.target.value)} />
            {filteredLeagues.length === 0 && <p className="muted">Nenhuma liga. Sincronize uma liga na aba Sofascore.</p>}
            {groupedByContinent.map(([continentName, list]) => {
              const open = openConts.has(continentName)
              return (
                <div key={continentName} className="league-group continent">
                  <button className="continent-toggle" onClick={() => toggleCont(continentName)}>
                    <span className={open ? 'chev open' : 'chev'}>▸</span>
                    <span className="continent-label">🌍 {continentName}</span>
                    <span className="muted small">({list.length})</span>
                  </button>
                  {open && (
                    <div className="continent-body">
                      {Object.entries(list.reduce((acc, l) => {
                        const c = l.country || 'Outros'
                        ;(acc[c] = acc[c] || []).push(l)
                        return acc
                      }, {})).sort((a, b) => a[0].localeCompare(b[0])).map(([country, clist]) => (
                        <div key={country} className="league-group">
                          <div className="league-group-title">{flag(country)} {country} <span className="muted small">({clist.length})</span></div>
                          <ul className="league-list">
                            {clist.map(l => (
                              <li key={l.id} className={selLeague === l.id ? 'active' : ''} onClick={() => selectLeague(l.id)}>
                                <span className="name">{l.name}</span>
                                <span className="meta">{l.played} jogos · {l.scheduled} agendados</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </aside>

          <section className="content">
            <section className="panel">
              <h3>Montar Confronto</h3>
              <div className="cf-form">
                <label>
                  Liga
                  <select value={cfLeague} onChange={e => onCfLeagueChange(e.target.value)}>
                    <option value="">— selecione —</option>
                    {leagues.map(l => (
                      <option key={l.id} value={l.id}>
                        {flag(l.country)} {l.name} ({l.played} jogos)
                      </option>
                    ))}
                  </select>
                </label>
                <button className="btn-small btn-demand" onClick={onCfDemand} disabled={loading || !cfLeague} title="Sincronizar esta liga no Sofascore">
                  {loading ? 'Sincronizando...' : '📥 Sincronizar dados'}
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
                <p className="muted small">Nenhum time nesta liga ainda. Use "Sincronizar dados" para puxar os jogos do Sofascore.</p>
              )}
            </section>

            {prediction && (
              <PredictionView p={prediction} token={token} onSave={onSavePrediction} />
            )}

            {selLeague && selLeagueObj && (
              <section className="panel">
                <h3>{flag(selLeagueObj.country)} {selLeagueObj.name} — Partidas</h3>
                <div className="table-scroll">
                  <table className="matches">
                    <thead>
                      <tr><th>Data</th><th>Casa</th><th>Placar</th><th>Fora</th><th></th></tr>
                    </thead>
                    <tbody>
                      {matches.map(m => (
                        <tr key={m.id}>
                          <td>{m.match_date}</td>
                          <td>{m.home}</td>
                          <td>{m.status === 'played' ? `${m.score_home} - ${m.score_away}` : '—'}</td>
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
              </section>
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

      {tab === 'aprendizado' && (
        <main className="column">
          <section className="panel">
            <div className="panel-head">
              <div>
                <h3>🧠 Aprendizado do motor</h3>
                <p className="muted small">Fator de mando (HA) e janela deslizante calibrados por liga via backtest honesto (prevê cada jogo usando só os jogos anteriores).</p>
              </div>
              <button className="btn-primary" onClick={startCalibration} disabled={loading || (cal && cal.running)}>
                {cal && cal.running ? `Calibrando ${cal.done}/${cal.total}...` : '⚡ Recalibrar todas'}
              </button>
            </div>

            {learn && <NeuralNet learn={learn} cal={cal} />}

            {!learn && <div className="muted small" style={{ padding: '14px 0' }}>Carregando estado do aprendizado...</div>}

            {cal && cal.running && (
              <div className="batch-progress">
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${cal.total ? (cal.done / cal.total) * 100 : 0}%` }} />
                </div>
                <p className="muted small">{cal.done}/{cal.total} ligas{cal.current ? ` · agora: ${cal.current}` : ''}</p>
              </div>
            )}

            {learn && (
              <>
                <div className="hist-stats">
                  <Stat label="Ligas calibradas" value={learn.calibrated_count} ok />
                  <Stat label="Grid (HA)" value={learn.grid.home_advantage.map(String).join(', ')} />
                  <Stat label="Janelas" value={learn.grid.window.map(String).join(', ')} />
                </div>
                <div className="table-scroll" style={{ marginTop: 14 }}>
                  <table className="runs">
                    <thead>
                      <tr><th>Liga</th><th>Feature</th><th>HA</th><th>Janela</th><th>Acurácia</th><th>Brier</th><th>Amostras</th><th>Calibrada</th><th></th></tr>
                    </thead>
                    <tbody>
                      {[...learn.calibrated]
                        .sort((a, b) => (b.accuracy || 0) - (a.accuracy || 0))
                        .map(lm => (
                          <tr key={lm.league_id}>
                            <td><b>{lm.name}</b></td>
                            <td>{lm.feature}</td>
                            <td>{Number(lm.home_advantage).toFixed(2)}</td>
                            <td>{lm.window}</td>
                            <td>{lm.accuracy ? `${lm.accuracy.toFixed(1)}%` : '—'}</td>
                            <td>{lm.brier ? lm.brier.toFixed(3) : '—'}</td>
                            <td>{lm.sample_count}</td>
                            <td>{lm.calibrated_at || '—'}</td>
                            <td><button className="btn-small" onClick={() => runBacktest(lm.league_id)} disabled={backtesting}>Reavaliar</button></td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {backtest && (
              <div className="card" style={{ marginTop: 14 }}>
                <h4>📊 Backtest da liga</h4>
                <div className="hist-stats">
                  <Stat label="Amostras" value={backtest.total} />
                  <Stat label="Acertos" value={backtest.correct} ok />
                  <Stat label="Acurácia" value={`${backtest.accuracy.toFixed(1)}%`} ok />
                  <Stat label="Brier" value={backtest.brier.toFixed(3)} />
                </div>
                <p className="muted small">Reavaliação com o modelo padrão (xG, HA 1.15, janela 10).</p>
                {backtest.series && backtest.series.length > 1 && (
                  <LineChart data={backtest.series.map(s => ({ x: s.n, y: s.acc }))}
                             title={`Curva de aprendizado real · ${backtest.total} previsões`}
                             xLabel="previsões acumuladas" yLabel="acurácia %" />
                )}
              </div>
            )}

            <section className="card" style={{ marginTop: 14 }}>
              <div className="panel-head">
                <div>
                  <h4>📈 Linha de aprendizado real do motor</h4>
                  <p className="muted small">
                    Acurácia acumulada média (1X2) por % de temporada, calculada com o backtest
                    honesto em todas as ligas calibradas — cada liga com o seu modelo (feature, HA, janela).
                  </p>
                </div>
                <button className="btn-small" onClick={loadCurve} disabled={curveLoading || (cal && cal.running)}>
                  {curveLoading ? 'Calculando...' : (curve ? '🔄 Recalcular' : '📈 Calcular curva')}
                </button>
              </div>
              {curve && curve.series.length > 1 ? (
                <>
                  <LineChart data={curve.series.map(s => ({ x: s.pct, y: s.acc }))}
                             title={`Curva média · ${curve.total_leagues} ligas · ${curve.total_played} jogos`}
                             xLabel="% da temporada" yLabel="acurácia %" />
                  <p className="muted small" style={{ marginTop: 8 }}>
                    Ponto final ({curve.series[curve.series.length - 1]?.pct}%):{' '}
                    <b>{curve.series[curve.series.length - 1]?.acc}%</b> de acurácia média.
                  </p>
                </>
              ) : curve && (
                <p className="muted small" style={{ padding: '12px 0' }}>
                  Sem ligas com dados suficientes ainda. Sincronize mais jogos (mín. {learn?.min_samples || 30} por liga).
                </p>
              )}
              {!curve && !curveLoading && (
                <p className="muted small" style={{ padding: '12px 0' }}>
                  Clique em "Calcular curva" para ver como a acurácia do motor evolui conforme ele vê mais jogos.
                </p>
              )}
            </section>
          </section>
        </main>
      )}

      {tab === 'dados' && (
        <main className="column">
          <section className="panel">
            <div className="panel-head">
              <div>
                <h3>🗄️ Dados no banco</h3>
                <p className="muted small">Ligas sincronizadas do Sofascore: jogos jogados/agendados, temporada ativa, último sync e estado do modelo calibrado.</p>
              </div>
              <button className="btn-small" onClick={() => { refreshLeagues(); loadLearning() }}>🔄 Atualizar</button>
            </div>
            <div className="table-scroll">
              <table className="runs">
                <thead>
                  <tr><th>Liga</th><th>País</th><th>Jogados</th><th>Agendados</th><th>Temporada</th><th>Último sync</th><th>Feature</th><th>HA</th><th>Jan</th><th>Acur.</th><th>Brier</th></tr>
                </thead>
                <tbody>
                  {leagues.map(r => {
                    const lm = learn?.calibrated?.find(m => m.league_id === r.id)
                    return (
                      <tr key={r.id}>
                        <td><b>{r.name}</b></td>
                        <td>{flag(r.country)} {r.country || '—'}</td>
                        <td>{r.played}</td>
                        <td>{r.scheduled}</td>
                        <td>{r.season_name || '—'}</td>
                        <td>{r.last_sync || '—'}</td>
                        <td>{lm?.feature || '—'}</td>
                        <td>{lm?.home_advantage != null ? Number(lm.home_advantage).toFixed(2) : '—'}</td>
                        <td>{lm?.window || '—'}</td>
                        <td>{lm?.accuracy ? `${lm.accuracy.toFixed(1)}%` : '—'}</td>
                        <td>{lm?.brier != null ? lm.brier.toFixed(3) : '—'}</td>
                      </tr>
                    )
                  })}
                  {leagues.length === 0 && (
                    <tr><td colSpan={11} className="muted">Nenhuma liga sincronizada ainda. Use a aba Sofascore para puxar os dados.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </main>
      )}

      {tab === 'sofascore' && (
        <main className="column">
          <section className="panel">
            <div className="panel-head">
              <div>
                <h3>📊 Sofascore — dados ricos por jogo</h3>
                <p className="muted small">
                  Todas as ligas configuradas via API do Sofascore (xG, posse, chutes, passes, escanteios...).
                  Marque as métricas que importam para filtrar e comparar.
                </p>
              </div>
              <div className="btn-row">
                <label className="inline">
                  Liga
                  <select value={sofaLeague} onChange={e => {
                    const v = e.target.value
                    setSofaLeague(v)
                    loadSofa(v || undefined)
                  }}>
                    <option value="">Todas</option>
                    {leagues.map(l => (
                      <option key={l.id} value={l.id}>{flag(l.country)} {l.name}</option>
                    ))}
                  </select>
                </label>
                {sofaLeague && (
                  <button className="btn-primary" onClick={() => startSofaSync(sofaLeague)}
                          disabled={loading || (sofaStatus && sofaStatus.running)}>
                    📥 Sync liga
                  </button>
                )}
                <button className="btn-primary" onClick={() => startSofaSync()}
                        disabled={loading || (sofaStatus && sofaStatus.running)}>
                  {sofaStatus && sofaStatus.running ? `Sincronizando ${sofaStatus.done}/${sofaStatus.total}...` : '📥 Sincronizar tudo'}
                </button>
              </div>
            </div>

            {sofaStatus && sofaStatus.running && (
              <div className="batch-progress">
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${sofaStatus.total ? (sofaStatus.done / sofaStatus.total) * 100 : 0}%` }} />
                </div>
                <p className="muted small">{sofaStatus.done}/{sofaStatus.total} ligas · {sofaStatus.ok} ok · {sofaStatus.fail} falhas{sofaStatus.current ? ` · agora: ${sofaStatus.current}` : ''}</p>
              </div>
            )}
            {sofaStatus && !sofaStatus.running && sofaStatus.error && (
              <p className="error" style={{ marginTop: 8 }}>✕ {sofaStatus.error}</p>
            )}
            {sofaStatus && !sofaStatus.running && sofaStatus.finished_at && sofaStatus.errors?.length > 0 && (
              <p className="muted small" style={{ marginTop: 8, color: '#fbbf24' }}>
                ⚠️ Liga(s) com falha: {sofaStatus.errors.map(e => e.league).join(', ')}
              </p>
            )}
            {sofa && sofa.length > 0 && (
              <p className="muted small" style={{ marginTop: 8 }}>
                ✅ {sofa.length} jogos carregados
                {sofaStatus?.finished_at ? ` · sincronizado em ${sofaStatus.finished_at}` : ''}
              </p>
            )}

            {sofa && sofa.length > 0 && (
              <>
                <div className="cf-form" style={{ flexWrap: 'wrap', marginTop: 10 }}>
                  <label>
                    Time
                    <input className="search" style={{ width: 180 }} placeholder="Buscar time..."
                           value={sofaTeamFilter} onChange={e => setSofaTeamFilter(e.target.value)} />
                  </label>
                  <label>
                    Rodada
                    <select value={sofaRoundFilter} onChange={e => setSofaRoundFilter(e.target.value)}>
                      <option value="">Todas</option>
                      {[...new Set(sofa.map(m => m.round).filter(r => r != null))].sort((a, b) => a - b).map(r => (
                        <option key={r} value={r}>Rodada {r}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Métricas
                    <select multiple size={6} style={{ height: 120, width: 220 }} value={sofaSelFields}
                            onChange={e => {
                              const v = [...e.target.options].filter(o => o.selected).map(o => o.value)
                              setSofaSelFields(v)
                            }}>
                      {Object.entries(STAT_LABELS).map(([k, label]) => (
                        <option key={k} value={k}>{label}</option>
                      ))}
                    </select>
                  </label>
                </div>

                <div className="table-scroll" style={{ marginTop: 12 }}>
                  <table className="runs sofa">
                    <thead>
                      <tr>
                        <th>Rod</th>
                        <th>Data</th>
                        <th>Placar</th>
                        <th>Casa</th>
                        {sofaSelFields.map(f => (
                          <th key={f} className="num" title={STAT_LABELS[f]}>{STAT_LABELS[f]} C</th>
                        ))}
                        <th>Fora</th>
                        {sofaSelFields.map(f => (
                          <th key={f} className="num" title={STAT_LABELS[f]}>{STAT_LABELS[f]} F</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sofa
                        .filter(m => !sofaTeamFilter.trim()
                          || m.home.toLowerCase().includes(sofaTeamFilter.trim().toLowerCase())
                          || m.away.toLowerCase().includes(sofaTeamFilter.trim().toLowerCase()))
                        .filter(m => !sofaRoundFilter || String(m.round) === sofaRoundFilter)
                        .map(m => (
                          <tr key={m.id}>
                            <td>{m.round}</td>
                            <td>{m.match_date}</td>
                            <td className="score">{m.score_home ?? '—'} - {m.score_away ?? '—'}</td>
                            <td><b>{m.home}</b></td>
                            {sofaSelFields.map(f => (
                              <td key={f} className="num">{m[`${f}_home`] != null ? Number(m[`${f}_home`]).toFixed(Number(m[`${f}_home`]) % 1 ? 1 : 0) : '—'}</td>
                            ))}
                            <td><b>{m.away}</b></td>
                            {sofaSelFields.map(f => (
                              <td key={f} className="num">{m[`${f}_away`] != null ? Number(m[`${f}_away`]).toFixed(Number(m[`${f}_away`]) % 1 ? 1 : 0) : '—'}</td>
                            ))}
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {(!sofa || sofa.length === 0) && !sofaStatus?.running && (
              <p className="muted small" style={{ padding: '14px 0' }}>
                Nenhum dado ainda. Clique em "Sincronizar tudo" para puxar os jogos de todas as ligas do Sofascore.
              </p>
            )}
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

function LineChart({ data, title, xLabel, yLabel }) {
  const W = 560, H = 220, P = 34
  const xs = data.map(d => d.x)
  const ys = data.map(d => d.y)
  const minX = Math.min(...xs), maxX = Math.max(...xs)
  const minY = Math.min(...ys, 0), maxY = Math.max(...ys)
  const yPad = Math.max((maxY - minY) * 0.15, 2)
  const loY = Math.max(0, minY - yPad), hiY = maxY + yPad
  const spanX = (maxX - minX) || 1, spanY = (hiY - loY) || 1
  const px = x => P + (x - minX) / spanX * (W - P * 2)
  const py = y => H - P - (y - loY) / spanY * (H - P * 2)
  const line = data.map((d, i) => `${i === 0 ? 'M' : 'L'}${px(d.x).toFixed(1)},${py(d.y).toFixed(1)}`).join(' ')
  const area = `${line} L${px(maxX).toFixed(1)},${py(loY).toFixed(1)} L${px(minX).toFixed(1)},${py(loY).toFixed(1)} Z`
  const last = data[data.length - 1]

  const yTicks = [0, 25, 50, 75, 100].filter(t => t >= loY && t <= hiY)

  return (
    <div className="chart-card">
      <div className="chart-title">{title}</div>
      <svg viewBox={`0 0 ${W} ${H}`} className="line-chart">
        {yTicks.map(t => (
          <g key={t}>
            <line x1={P} x2={W - P} y1={py(t)} y2={py(t)} stroke="rgba(148,163,184,.15)" strokeDasharray="3 4" />
            <text x={P - 6} y={py(t) + 3} textAnchor="end" fill="#94a3b8" fontSize="10">{t}</text>
          </g>
        ))}
        <path d={area} fill="rgba(52,211,153,.10)" stroke="none" />
        <path d={line} fill="none" stroke="#34d399" strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={px(last.x)} cy={py(last.y)} r="4" fill="#34d399" />
        <text x={px(last.x) - 6} y={py(last.y) - 8} textAnchor="end" fill="#34d399" fontSize="11" fontWeight="bold">
          {last.y.toFixed(1)}%
        </text>
        <text x={P} y={H - 4} fill="#94a3b8" fontSize="10">{xLabel} · de {minX} a {maxX}</text>
        <text x={W - P} y={12} textAnchor="end" fill="#94a3b8" fontSize="10">{yLabel}</text>
      </svg>
    </div>
  )
}

function NeuralNet({ learn, cal }) {
  const running = cal?.running || false
  const total = learn?.calibrated?.length || 0
  const acc = total ? learn.calibrated.reduce((s, m) => s + (m.accuracy || 0), 0) / total : 0
  const grid = learn?.grid?.home_advantage?.length || 7
  const listen = Math.max(3, Math.min(8, Math.round(total / 6)))
  const layers = [grid, Math.max(8, Math.min(16, Math.round(total / 4))), listen, 3]
  const xs = [60, 165, 270, 330]
  const cols = ['#22d3ee', '#4ade80', '#fbbf24', '#a78bfa']
  const ys = []
  layers.forEach((n, li) => {
    const arr = []
    for (let i = 0; i < n; i++) arr.push(40 + (220 / (n - 1 || 1)) * i)
    ys.push(arr)
  })
  const edges = []
  for (let l = 0; l < 3; l++) {
    ys[l].forEach((a, i) => {
      ys[l + 1].forEach((b, j) => {
        edges.push({ x1: xs[l], y1: a, x2: xs[l + 1], y2: b, k: (i + j) % 5 })
      })
    })
  }
  const nodes = []
  for (let l = 0; l < 4; l++) {
    ys[l].forEach((y, i) => {
      const active = running || (l === 0 ? i < grid : l === 1 ? i < Math.ceil(total / 4) : l === 2 ? i < listen : i < 2)
      nodes.push({ x: xs[l], y, l, active })
    })
  }
  return (
    <div className="neural-wrap">
      <svg viewBox="0 0 380 300" className="neural">
        <defs>
          <linearGradient id="ng" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#22d3ee" />
            <stop offset="1" stopColor="#a78bfa" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="380" height="300" rx="14" fill="rgba(8,10,24,.6)" stroke="rgba(148,163,184,.18)" />
        {edges.map((e, i) => (
          <line key={i} x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2}
                stroke={cols[e.k % 3]} strokeOpacity={running ? 0.25 : 0.12} strokeWidth="1"
                className={running ? 'nn-edge' : ''} style={{ animationDelay: `${(e.k * 0.15).toFixed(2)}s` }} />
        ))}
        {nodes.map((n, i) => (
          <g key={i}>
            <circle cx={n.x} cy={n.y} r="7" fill={cols[n.l]} className={n.active && running ? 'nn-node' : ''}
                    style={n.active && running ? { animationDelay: `${(n.y * 0.01).toFixed(2)}s` } : {}} />
            <circle cx={n.x} cy={n.y} r="7" fill="none" stroke={cols[n.l]}
                    strokeOpacity={n.active ? 0.9 : 0.28} strokeWidth="1.5" />
          </g>
        ))}
        <text x="60" y="292" textAnchor="middle" fill="#94a3b8" fontSize="11">entrada</text>
        <text x="165" y="292" textAnchor="middle" fill="#94a3b8" fontSize="11">oculta</text>
        <text x="270" y="292" textAnchor="middle" fill="#94a3b8" fontSize="11">escuta</text>
        <text x="330" y="292" textAnchor="middle" fill="#94a3b8" fontSize="11">saída</text>
      </svg>
      <div className="neural-meta">
        <span className="neural-dot" style={{ background: '#4ade80' }}></span>
        <span className="muted small">{total} ligas calibradas</span>
        <span className="neural-dot" style={{ background: '#22d3ee' }}></span>
        <span className="muted small">acurácia média {acc.toFixed(1)}%</span>
        <span className="neural-dot" style={{ background: running ? '#fbbf24' : '#64748b' }}></span>
        <span className="muted small">{running ? `aprendendo ${cal.done}/${cal.total}...` : 'em repouso'}</span>
      </div>
    </div>
  )
}

function PredictionView({ p, token, onSave }) {
  const { match, lambdas, probs, top_scores, proposals, compare, model } = p
  const [picked, setPicked] = useState(null)
  const [chestOpen, setChestOpen] = useState(false)

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

      {model && (model.accuracy != null || model.home_advantage) && (
        <div className="model-chip">
          🧠 modelo {match.league}: {model.feature || 'xg'} · HA {Number(model.home_advantage).toFixed(2)} · janela {model.window}
          {model.accuracy != null && <> · acurácia {Number(model.accuracy).toFixed(1)}%</>}
          {model.brier != null && <> · Brier {Number(model.brier).toFixed(3)}</>}
        </div>
      )}

      {compare && compare.h2h?.length > 0 && (
        <div className="card h2h">
          <h4>⚔️ Confrontos diretos</h4>
          <div className="h2h-row">
            {compare.h2h.slice(0, 5).map((m, i) => (
              <div className="h2h-item" key={i}>
                <span className="h2h-date">{m.match_date}</span>
                <span>{m.home} <b>{m.score_home}–{m.score_away}</b> {m.away}</span>
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

        <div className="data-chest">
          <button className="chest-toggle" onClick={() => setChestOpen(!chestOpen)}>
            <span>🗄️ Baú de dados deste confronto</span>
            <span className={chestOpen ? 'chest-arrow open' : 'chest-arrow'}>{chestOpen ? '▲' : '▼'}</span>
          </button>
          {chestOpen && p.data && (
            <div className="chest-body">
              <div className="chest-grid">
                <div>
                  <h4>📌 Dados usados nas médias (λ)</h4>
                  <p className="muted small">Fonte: {p.data.source || 'sofascore'} · janela {p.data.model.window} · HA {Number(p.data.model.home_advantage).toFixed(2)}</p>
                  {['home', 'away'].map(side => {
                    const d = p.data[side]
                    return (
                      <div key={side} className="chest-team">
                        <b>{d.name}</b>
                        <span className="muted small">média GF {d.avg.gf_avg} · GA {d.avg.ga_avg} · {d.count} jogos usados</span>
                        <table className="mini">
                          <tbody>
                            <tr><th>Data</th><th>Lado</th><th>Adversário</th><th>GF</th><th>GA</th></tr>
                            {d.games_used.map((g, i) => (
                              <tr key={i}>
                                <td>{g.date}</td><td>{g.side}</td><td>{g.opponent}</td>
                                <td>{g.gf}</td><td>{g.ga}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )
                  })}
                </div>
                <div>
                  <h4>⚔️ Confrontos diretos ({p.data.h2h.length})</h4>
                  {p.data.h2h.length === 0 && <p className="muted small">Sem confrontos diretos no banco.</p>}
                  <table className="mini">
                    <tbody>
                      <tr><th>Data</th><th>Casa</th><th>Fora</th><th>Placar</th></tr>
                      {p.data.h2h.map((g, i) => (
                        <tr key={i}><td>{g.match_date}</td><td>{g.home}</td><td>{g.away}</td><td>{g.score_home}-{g.score_away}</td></tr>
                      ))}
                    </tbody>
                  </table>
                  <h4 style={{ marginTop: 14 }}>📈 Forma recente</h4>
                  {['home', 'away'].map(side => {
                    const d = p.data.form[side]
                    return (
                      <div key={side}>
                        <b className="small">{side === 'home' ? match.home : match.away}</b>
                        <div className="form-dots">
                          {d.map((g, i) => (
                            <span key={i} className={`fdot ${g.result === 'W' ? 'w' : g.result === 'D' ? 'd' : 'l'}`}
                                  title={`${g.date} vs ${g.opponent} (${g.gf}-${g.ga})`}>
                              {g.result}
                            </span>
                          ))}
                        </div>
                      </div>
                    )
                  })}
                  <h4 style={{ marginTop: 14 }}>🧠 Modelo calibrado</h4>
                  <p className="muted small">
                    {p.data.model.feature || 'xg'} · HA {Number(p.data.model.home_advantage).toFixed(2)} · janela {p.data.model.window}
                    {p.data.model.accuracy != null && <> · acurácia {Number(p.data.model.accuracy).toFixed(1)}%</>}
                    {p.data.model.brier != null && <> · Brier {Number(p.data.model.brier).toFixed(3)}</>}
                  </p>
                </div>
              </div>
              <details className="chest-raw">
                <summary>🔍 JSON completo (tudo sem exceção)</summary>
                <pre>{JSON.stringify(p.data, null, 2)}</pre>
              </details>
            </div>
          )}
          {chestOpen && !p.data && <div className="chest-body muted small">Dados não disponíveis para este confronto.</div>}
        </div>
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