import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { api, setOnUnauthorized } from './api.js'
import { usePolling } from './hooks/usePolling.js'

export default function App() {
  const [username, setUsername] = useState(null)
  const [role, setRole] = useState('user')
  const [restoring, setRestoring] = useState(true)

  useEffect(() => {
    let active = true
    // Restauração de sessão via cookie HttpOnly (sem token em localStorage).
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
  India: '🇮🇳', Vietnam: '🇻🇳', 'South Africa': '🇿🇦', Iceland: '🇮🇸', Latvia: '🇱🇻',
  Bulgaria: '🇧🇬', Israel: '🇮🇱', Slovenia: '🇸🇮', Wales: '🏴󠁧󠁢󠁷󠁬󠁳󠁿', 'Northern Ireland': '🇬🇧',
  Malta: '🇲🇹', Panama: '🇵🇦',
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
  Bulgaria: 'Europa', Israel: 'Ásia', Slovenia: 'Europa', Iceland: 'Europa',
  Latvia: 'Europa', Wales: 'Europa', 'Northern Ireland': 'Europa', Malta: 'Europa',
  India: 'Ásia', Vietnam: 'Ásia', 'South Africa': 'África',
  Panama: 'América do Norte',
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

const METHOD_META = {
  bayesian: { icon: '🧠', label: 'Bayesiano' },
  hybrid: { icon: '⚖️', label: 'Híbrido' },
  poisson: { icon: '🎲', label: 'Poisson' },
}

function methodBadge(method) {
  const m = METHOD_META[method] || METHOD_META.poisson
  return <span className={`badge method-${method || 'poisson'}`}>{m.icon} {m.label}</span>
}

const CTX_META = [
  ['ctx_rest', '😴 descanso'],
  ['ctx_form', '📈 forma'],
  ['ctx_team_ha', '🏟️ mando'],
]

function ctxChips(ctx) {
  if (!ctx) return <span className="muted">—</span>
  const on = CTX_META.filter(([k]) => ctx[k] || ctx[k.replace('ctx_', '')]).map(([, label]) => label)
  if (on.length === 0) return <span className="muted small">base</span>
  return on.join(' · ')
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

function Dashboard({ username, role, token, onLogout }) {
  const [tab, setTab] = useState('confronto')
  const [showMethodNotice, setShowMethodNotice] = useState(true)
  const canOperate = role === 'operator' || role === 'admin'
  const roleLabel = role === 'admin' ? 'Administrador' : role === 'operator' ? 'Operador' : 'Leitor'
  const operationHint = canOperate
    ? ''
    : 'Esta ação exige papel de operador ou administrador.'
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
  const [backtest, setBacktest] = useState(null)
  const [backtesting, setBacktesting] = useState(false)
  const [curve, setCurve] = useState(null)
  const [curveLoading, setCurveLoading] = useState(false)

  const [sofa, setSofa] = useState(null)
  const [sofaStatus, setSofaStatus] = useState(null)
  const [sofaLeague, setSofaLeague] = useState('')
  const [sofaSelFields, setSofaSelFields] = useState(['xg', 'possession', 'shots_on_target', 'corners', 'yellow_cards'])
  const [sofaTeamFilter, setSofaTeamFilter] = useState('')

  const [histLoading, setHistLoading] = useState(false)

  const [evol, setEvol] = useState(null)
  const [evolLoading, setEvolLoading] = useState(false)
  const [evolHist, setEvolHist] = useState(null)

  const [btStatus, setBtStatus] = useState(null)
  const [btJob, setBtJob] = useState(null)
  const [btHistory, setBtHistory] = useState(null)
  const [btMeta, setBtMeta] = useState(null)
  const [btCvResult, setBtCvResult] = useState(null)
  const [btRunning, setBtRunning] = useState(false)
  const [btInterval, setBtInterval] = useState(6)
  const [btSummary, setBtSummary] = useState(null)

  const refreshLeagues = useCallback(async () => {
    const raw = await api.leagues(token)
    // Deduplicate by league id — sem spread de iterador (bug de transpilação esbuild)
    const byId = {}
    raw.forEach(l => { byId[l.id] = l })
    setLeagues(Object.values(byId))
  }, [token])

  const loadHistory = useCallback(async () => {
    setHistLoading(true)
    try { setHist(await api.predictions(token)) } catch (e) { setError(e.message) }
    setHistLoading(false)
  }, [token])

  const loadLearning = useCallback(async () => {
    try { setLearn(await api.learningStatus(token)) } catch (e) { setError(e.message) }
  }, [token])

  const loadSofa = useCallback(async (leagueId) => {
    try { setSofa(await api.sofascoreData(leagueId, token)) } catch (e) { setError(e.message) }
  }, [token])

  useEffect(() => {
    refreshLeagues().catch(e => setError(e.message))
    if (tab === 'historico') loadHistory()
    if (tab === 'aprendizado') loadLearning()
    if (tab === 'sofascore') loadSofa()
  }, [tab, refreshLeagues, loadHistory, loadLearning, loadSofa])

  usePolling(opts => api.job(sofaStatus?.id, token, opts), {
    enabled: Boolean(sofaStatus?.id && ['pending', 'running'].includes(sofaStatus.status)),
    stopWhen: j => !['pending', 'running'].includes(j.status),
    onTick: j => { setSofaStatus(j); if (!['pending', 'running'].includes(j.status)) loadSofa(sofaLeague || undefined) },
    onError: e => setError(e.message),
  })
  usePolling(opts => api.job(cal?.id, token, opts), {
    enabled: Boolean(cal?.id && ['pending', 'running'].includes(cal.status)), interval: 3000,
    stopWhen: j => !['pending', 'running'].includes(j.status),
    onTick: j => { setCal(j); if (!['pending', 'running'].includes(j.status)) loadLearning() },
    onError: e => setError(e.message),
  })
  usePolling(opts => api.job(btJob?.id, token, opts), {
    enabled: Boolean(btJob?.id && ['pending', 'running'].includes(btJob.status)), interval: 3000,
    stopWhen: j => !['pending', 'running'].includes(j.status),
    onTick: j => { setBtJob(j); if (!['pending', 'running'].includes(j.status)) loadBtStatus() },
    onError: e => setError(e.message),
  })

  async function startSofaSync(leagueId) {
    setLoading(true); setError('')
    try {
      const res = leagueId ? await api.sofascoreSyncLeague(leagueId, token) : await api.sofascoreSync(token)
      setSofaStatus(res.job)
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  async function startCalibration() {
    setLoading(true); setError('')
    try {
      const res = await api.learningCalibrate(token)
      setCal(res.job)
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

  async function loadEvolution() {
    setEvolLoading(true); setError('')
    try {
      setEvol(await api.evolutionSnapshot(token))
    } catch (e) { setError(e.message) }
    setEvolLoading(false)
  }

  async function loadEvolutionHistory() {
    try {
      setEvolHist(await api.evolutionHistory(50, token))
    } catch (_e) { /* histórico é opcional — não bloqueia a aba */ }
  }

  async function loadBtStatus() {
    try { setBtStatus(await api.backtestStatus(token)) } catch (e) { setError(e.message) }
    try { setBtHistory(await api.backtestHistory(10, token)) } catch (_e) {}
    try { setBtMeta(await api.backtestMeta(token)) } catch (_e) {}
    try { setBtSummary(await api.backtestSummary(token)) } catch (_e) {}
  }

  async function startBtLoop() {
    setBtRunning(true); setError('')
    try {
      const res = await api.backtestStart(btInterval, token)
      setBtJob(res.job)
      setBtStatus(previous => ({ ...previous, running: true }))
    } catch (e) { setError(e.message) }
    setBtRunning(false)
  }

  async function stopBtLoop() {
    try {
      if (btJob?.id && ['pending', 'running'].includes(btJob.status)) {
        await api.cancelJob(btJob.id, token)
        setBtJob(previous => ({ ...previous, status: 'cancelled' }))
      }
      loadBtStatus()
    } catch (e) { setError(e.message) }
  }

  async function runBtCycle(leagueIds = null) {
    setBtRunning(true); setError(''); setBtCvResult(null)
    try {
      const result = await api.backtestRun(leagueIds, token)
      setBtJob(result.job)
      setBtCvResult(result.job)
      loadBtStatus()
    } catch (e) { setError(e.message) }
    setBtRunning(false)
  }

  async function runBtCV(leagueId) {
    setBtRunning(true); setError(''); setBtCvResult(null)
    try {
      const cv = await api.backtestCV(leagueId, 5, token)
      setBtCvResult(cv)
    } catch (e) { setError(e.message) }
    setBtRunning(false)
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
      if (res.ok) {
        setSofaStatus(res.job)
        alert(`Sincronização enfileirada: job ${res.job_id}. Acompanhe na aba Sofascore.`)
      }
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
          <button className={tab === 'evolucao' ? 'active' : ''} onClick={() => { setTab('evolucao'); loadEvolution(); loadEvolutionHistory() }}>📈 Evolução</button>
          <button className={tab === 'backtest' ? 'active' : ''} onClick={() => { setTab('backtest'); loadBtStatus() }}>🔬 Backtest Engine</button>
        </nav>
        <div className="user">
          <span>{username}</span>
          <span className={`role-badge role-${role}`}>{roleLabel}</span>
          <button type="button" className="btn-link" onClick={onLogout} aria-label="Sair da conta">Sair</button>
        </div>
      </header>
      {error && <div className="error banner" onClick={() => setError('')}>✕ {error}</div>}

      {tab === 'confronto' && (
        <main>
          {showMethodNotice && (
            <div className="muted small" style={{ marginBottom: 12 }}>
              Motor experimental: probabilidades e odds justas sao informativas. Mercado, EV e Kelly exigem quote externa timestampada.
              <button className="btn-link" onClick={() => setShowMethodNotice(false)}>Ocultar</button>
            </div>
          )}
          <aside>
            <h3>Ligas no banco <span className="muted small">({leagues.length})</span></h3>
            <input className="search" placeholder="🔎 Buscar liga ou país..."
                   value={leagueSearch} onChange={e => setLeagueSearch(e.target.value)} />
            {filteredLeagues.length === 0 && <p className="muted">
              {canOperate
                ? 'Nenhuma liga. Sincronize uma liga na aba Sofascore.'
                : 'Nenhuma liga sincronizada. Peça a um operador para iniciar a sincronização.'}
            </p>}
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
                <button className="btn-small btn-demand" onClick={onCfDemand} disabled={!canOperate || loading || !cfLeague}
                        title={operationHint || 'Sincronizar esta liga no Sofascore'}>
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
              <button className="btn-small" onClick={loadHistory} disabled={histLoading}>
                {histLoading ? 'Carregando...' : 'Atualizar'}
              </button>
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
                       <td>Justa @{h.odd}</td>
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
              <button className="btn-primary" onClick={startCalibration}
                      disabled={!canOperate || loading || ['pending', 'running'].includes(cal?.status)} title={operationHint}>
                {['pending', 'running'].includes(cal?.status) ? `Calibrando ${Math.round((cal.progress || 0) * 100)}%...` : '⚡ Recalibrar todas'}
              </button>
            </div>

            {!learn && <div className="muted small" style={{ padding: '14px 0' }}>Carregando estado do aprendizado...</div>}

            {['pending', 'running'].includes(cal?.status) && (
              <div className="batch-progress">
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${(cal.progress || 0) * 100}%` }} />
                </div>
                <p className="muted small">{Math.round((cal.progress || 0) * 100)}%{cal.detail ? ` · ${cal.detail}` : ''}</p>
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
                      <tr><th>Liga</th><th>Feature</th><th>HA</th><th>Janela</th><th>Método</th><th>Contexto</th><th>Acurácia</th><th>Brier</th><th>Amostras</th><th>Calibrada</th><th></th></tr>
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
                            <td>{methodBadge(lm.method)}</td>
                            <td>{ctxChips(lm)}</td>
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
                <button className="btn-small" onClick={loadCurve} disabled={curveLoading || ['pending', 'running'].includes(cal?.status)}>
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
                  <tr><th>Liga</th><th>País</th><th>Jogados</th><th>Agendados</th><th>Temporada</th><th>Último sync</th><th>Feature</th><th>HA</th><th>Jan</th><th>Método</th><th>Ctx</th><th>Acur.</th><th>Brier</th></tr>
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
                        <td>{lm ? methodBadge(lm.method) : '—'}</td>
                        <td>{lm ? ctxChips(lm) : '—'}</td>
                        <td>{lm?.accuracy ? `${lm.accuracy.toFixed(1)}%` : '—'}</td>
                        <td>{lm?.brier != null ? lm.brier.toFixed(3) : '—'}</td>
                      </tr>
                    )
                  })}
                  {leagues.length === 0 && (
                    <tr><td colSpan={13} className="muted">Nenhuma liga sincronizada ainda. Use a aba Sofascore para puxar os dados.</td></tr>
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
                  Mostra somente a <b>próxima rodada</b> agendada de cada liga. Marque as métricas que importam para comparar.
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
                          disabled={!canOperate || loading || ['pending', 'running'].includes(sofaStatus?.status)} title={operationHint}>
                    📥 Sync liga
                  </button>
                )}
                <button className="btn-primary" onClick={() => startSofaSync()}
                        disabled={!canOperate || loading || ['pending', 'running'].includes(sofaStatus?.status)} title={operationHint}>
                  {['pending', 'running'].includes(sofaStatus?.status) ? `Sincronizando ${Math.round((sofaStatus.progress || 0) * 100)}%...` : '📥 Sincronizar tudo'}
                </button>
              </div>
            </div>

            {['pending', 'running'].includes(sofaStatus?.status) && (
              <div className="batch-progress">
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${(sofaStatus.progress || 0) * 100}%` }} />
                </div>
                <p className="muted small">{Math.round((sofaStatus.progress || 0) * 100)}%{sofaStatus.detail ? ` · ${sofaStatus.detail}` : ''}</p>
              </div>
            )}
            {sofaStatus && !['pending', 'running'].includes(sofaStatus.status) && sofaStatus.error_message && (
              <p className="error" style={{ marginTop: 8 }}>✕ {sofaStatus.error_message}</p>
            )}
            {sofaStatus && !['pending', 'running'].includes(sofaStatus.status) && sofaStatus.finished_at && sofaStatus.result?.errors?.length > 0 && (
              <p className="muted small" style={{ marginTop: 8, color: '#fbbf24' }}>
                ⚠️ Liga(s) com falha: {sofaStatus.result.errors.map(e => e.league).join(', ')}
              </p>
            )}
            {sofa && sofa.length > 0 && (
              <p className="muted small" style={{ marginTop: 8 }}>
                ✅ {sofa.length} jogos da próxima rodada
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

      {tab === 'evolucao' && (
        <main className="column">
          <section className="panel">
            <div className="panel-head">
              <div>
                <h3>📈 Monitor de Evolução</h3>
                <p className="muted small">
                  Compara as métricas atuais do motor (walk-forward honesto) contra o baseline armazenado.
                  Delta ≠ 0 = mudança real detectada — nada de impressão subjetiva.
                </p>
              </div>
              <button className="btn-small" onClick={() => { loadEvolution(); loadEvolutionHistory() }} disabled={evolLoading}>
                {evolLoading ? 'Medindo...' : '🔄 Atualizar agora'}
              </button>
            </div>

            {!evol && !evolLoading && (
              <p className="muted small" style={{ padding: '14px 0' }}>
                Clique em "Atualizar agora" para medir o estado atual e comparar com o baseline.
              </p>
            )}

            {evol && (
              <>
                <div className="hist-stats">
                  <Stat label="API" value={evol.current?.api_health ? 'online' : 'offline'} ok={evol.current?.api_health} bad={!evol.current?.api_health} />
                  <Stat label="Regressão" value={evol.current?.regression_suite || 'n/d*'}
                        title="Suíte selenium disponível apenas em dev (CLI)" />
                  <Stat label="Mudanças vs baseline" value={(evol.changes || []).length} ok={(evol.changes || []).length === 0} />
                  <Stat label="Snapshot" value={(evol.current?.timestamp || '').slice(0, 16).replace('T', ' ')} />
                </div>

                {(evol.changes || []).length > 0 && (
                  <div className="table-scroll" style={{ marginTop: 14 }}>
                    <h4 style={{ margin: '6px 0 10px' }}>⚡ Mudanças detectadas</h4>
                    <table className="runs">
                      <thead>
                        <tr><th>Métrica</th><th>Antes</th><th>Depois</th><th>Delta</th></tr>
                      </thead>
                      <tbody>
                        {evol.changes.map((c, i) => {
                          const good = typeof c.delta === 'number'
                            ? (c.metric.includes('accuracy') ? c.delta > 0 : c.delta < 0)
                            : null
                          return (
                            <tr key={i}>
                              <td><b>{c.metric}</b></td>
                              <td>{c.before}</td>
                              <td>{c.after}</td>
                              <td style={{ color: good == null ? '#94a3b8' : good ? '#34d399' : '#f87171', fontWeight: 700 }}>
                                {typeof c.delta === 'number' ? `${c.delta > 0 ? '+' : ''}${c.delta}` : c.delta}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                {(evol.changes || []).length === 0 && evol.baseline && (
                  <p className="muted small" style={{ marginTop: 12 }}>
                    ✅ Nenhuma mudança desde o último snapshot — sistema estável.
                  </p>
                )}

                {evol.current?.leagues && Object.keys(evol.current.leagues).length > 0 && (
                  <div className="table-scroll" style={{ marginTop: 14 }}>
                    <h4 style={{ margin: '6px 0 10px' }}>🎯 Métricas atuais por liga (walk-forward)</h4>
                    <table className="runs">
                      <thead>
                        <tr><th>Liga</th><th>Acurácia</th><th>Brier</th><th>LogLoss</th><th>Evolução</th></tr>
                      </thead>
                      <tbody>
                        {Object.entries(evol.current.leagues)
                          .filter(([_lid, m]) => !m.error)
                          .sort((a, b) => {
                            const accA = a[1].poisson_accuracy || 0
                            const accB = b[1].poisson_accuracy || 0
                            return accB - accA // Ordem decrescente (melhores no topo)
                          })
                          .map(([lid, m]) => {
                            const evo = evol.evolution?.[lid]
                            const accEvo = evo?.poisson_accuracy?.pct
                            const brierEvo = evo?.poisson_brier?.pct
                            // acurácia: +bom; brier/logloss: -bom
                            const formatEvo = (val, inverted) => {
                              if (val == null) return '—'
                              const sign = val > 0 ? '+' : ''
                              const color = inverted ? (val < 0 ? '#22c55e' : val > 0 ? '#ef4444' : '#94a3b8') : (val > 0 ? '#22c55e' : val < 0 ? '#ef4444' : '#94a3b8')
                              return <span style={{ color, fontWeight: 600 }}>{sign}{val.toFixed(2)}%</span>
                            }
                            return (
                              <tr key={lid}>
                                <td><b>{m.league_name || lid}</b></td>
                                <td>{m.poisson_accuracy}%</td>
                                <td>{m.poisson_brier}</td>
                                <td>{m.poisson_logloss ?? '—'}</td>
                                <td style={{ fontSize: '0.85em' }}>
                                  acc {formatEvo(accEvo, false)}<br/>
                                  brier {formatEvo(brierEvo, true)}
                                </td>
                              </tr>
                            )
                          })}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}

            {evolHist && evolHist.count > 1 && (() => {
              const lids = Object.keys(evolHist.series || {})
              return (
                <section className="card" style={{ marginTop: 16 }}>
                  <h4>📉 Tendência histórica ({evolHist.count} medições persistentes)</h4>
                  {lids.map(lid => {
                    const pts = evolHist.series[lid].filter(p => p.acc != null)
                    if (pts.length < 2) return null
                    const lname = evol.current?.leagues?.[lid]?.league_name || `Liga ${lid}`
                    return (
                      <LineChart key={lid}
                                 data={pts.map(p => ({ x: p.n, y: p.acc }))}
                                 title={`${lname} · acurácia ao longo das medições`}
                                 xLabel="medições" yLabel="acurácia %" />
                    )
                  })}
                  <p className="muted small" style={{ marginTop: 8 }}>
                    Cada medição (UI ou CLI) fica gravada em <code>backend/app/data/evolution_history.jsonl</code> — nada é sobrescrito.
                  </p>
                </section>
              )
            })()}

            {evolHist && evolHist.count <= 1 && (
              <p className="muted small" style={{ marginTop: 12 }}>
                Histórico tem {evolHist.count} medição(ões). Meça novamente em momentos diferentes (após calibrações, syncs ou mudanças de modelo) para gerar a curva de tendência.
              </p>
            )}
          </section>
        </main>
      )}

      {tab === 'backtest' && (
        <main className="column">
          <section className="panel">
            <div className="panel-head">
              <div>
                <h3>🔬 Backtest Engine</h3>
                <p className="muted small">
                  Execuções manuais experimentais de backtest e cross-validation temporal.
                  Resultados não promovem automaticamente modelos de produção.
                </p>
              </div>
              <div className="btn-row">
                <label className="inline">
                  Intervalo (horas)
                  <input type="number" value={btInterval} min={1} max={48}
                         onChange={e => setBtInterval(Number(e.target.value))}
                         style={{ width: 60 }} />
                </label>
                {btStatus?.running ? (
                  <button className="btn-small" onClick={stopBtLoop} disabled={!canOperate || !btStatus.running} title={operationHint}>
                    ⏹ Parar loop
                  </button>
                ) : (
                  <button className="btn-primary" onClick={startBtLoop} disabled={!canOperate || btRunning} title={operationHint}>
                    {btRunning ? 'Rodando...' : '▶ Iniciar loop'}
                  </button>
                )}
                <button className="btn-primary" onClick={() => runBtCycle()} disabled={!canOperate || btRunning} title={operationHint}>
                  {btRunning ? 'Rodando...' : '⚡ Rodar ciclo agora'}
                </button>
              </div>
            </div>

            {/* Status do loop */}
            {btStatus && (
              <div className="hist-stats" style={{ marginTop: 12 }}>
                <Stat label="Status" value={btStatus.running ? '🟢 Rodando' : '⏹ Parado'} ok={btStatus.running} />
                <Stat label="Ciclos" value={btStatus.cycle_count || 0} />
                <Stat label="Último ciclo" value={btStatus.last_cycle_at ? new Date(btStatus.last_cycle_at).toLocaleString() : 'nunca'} />
                <Stat label="Intervalo" value={`${btStatus.interval_hours || 6}h`} />
                <Stat label="Meta records" value={btStatus.meta_history_count || 0} />
              </div>
            )}

            {/* Fase atual */}
            {btStatus?.current_phase && btStatus.running && (
              <div className="batch-progress" style={{ marginTop: 12 }}>
                <p className="muted small">
                  🔄 {btStatus.current_phase}
                  {btStatus.current_league ? ` · ${btStatus.current_league}` : ''}
                </p>
              </div>
            )}

            {/* Resultado do último ciclo */}
            {btStatus?.cycle_results?.length > 0 && (
              <div className="table-scroll" style={{ marginTop: 14 }}>
                <h4 style={{ margin: '6px 0 10px' }}>📊 Resultados do último ciclo</h4>
                <table className="runs">
                  <thead>
                    <tr>
                      <th>Liga</th>
                      <th>Feature</th>
                      <th>HA</th>
                      <th>Jan</th>
                      <th>Rho</th>
                      <th>Accuracy</th>
                      <th>Brier</th>
                      <th>CV Brier</th>
                      <th>Promovido</th>
                    </tr>
                  </thead>
                  <tbody>
                    {btStatus.cycle_results.map((r, i) => (
                      <tr key={i}>
                        <td><b>{r.league_name}</b></td>
                        <td>{r.current_params?.feature}</td>
                        <td>{r.current_params?.home_advantage?.toFixed(2)}</td>
                        <td>{r.current_params?.window}</td>
                        <td>{r.current_params?.rho?.toFixed(3)}</td>
                        <td>{r.backtest?.accuracy?.toFixed(1)}%</td>
                        <td>{r.backtest?.brier?.toFixed(4)}</td>
                        <td>{r.cv?.mean_brier?.toFixed(4)}</td>
                        <td>{r.promoted ? '✅' : r.error ? '❌' : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Cross-Validation */}
          <section className="panel">
            <div className="panel-head">
              <div>
                <h4>📐 Cross-Validation Temporal</h4>
                <p className="muted small">
                  Validação em K folds cronológicos — treina no passado, testa no futuro.
                  Zero data leakage.
                </p>
              </div>
              <select value="" onChange={e => { if (e.target.value) runBtCV(Number(e.target.value)) }}
                      disabled={btRunning}>
                <option value="">Selecionar liga para CV...</option>
                {leagues.map(l => (
                  <option key={l.id} value={l.id}>{flag(l.country)} {l.name} ({l.played} jogos)</option>
                ))}
              </select>
            </div>

            {btCvResult && btCvResult.folds && (
              <div style={{ marginTop: 12 }}>
                <div className="hist-stats">
                  <Stat label="Acurácia média" value={`${btCvResult.mean_accuracy}%`} ok={btCvResult.mean_accuracy > 50} />
                  <Stat label="Brier médio" value={btCvResult.mean_brier?.toFixed(4)} />
                  <Stat label="Desvio acc" value={`±${btCvResult.std_accuracy}%`} />
                  <Stat label="Desvio Brier" value={`±${btCvResult.std_brier}`} />
                  <Stat label="Folds" value={btCvResult.n_folds} />
                </div>
                <div className="table-scroll" style={{ marginTop: 10 }}>
                  <table className="runs">
                    <thead>
                      <tr><th>Fold</th><th>Treino</th><th>Teste</th><th>Accuracy</th><th>Brier</th></tr>
                    </thead>
                    <tbody>
                      {btCvResult.folds.map(f => (
                        <tr key={f.fold}>
                          <td>Fold {f.fold}</td>
                          <td>{f.train_size} jogos</td>
                          <td>{f.test_size} jogos</td>
                          <td>{f.accuracy}%</td>
                          <td>{f.brier?.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {btCvResult && btCvResult.folds && btCvResult.folds.length > 1 && (
              <div style={{ marginTop: 12 }}>
                <LineChart
                  data={btCvResult.folds.map(f => ({ x: f.fold, y: f.accuracy }))}
                  title="Acurácia por fold temporal"
                  xLabel="Fold" yLabel="Acurácia %"
                />
              </div>
            )}
          </section>

          {/* Meta-Learning */}
          <section className="panel">
            <div className="panel-head">
              <div>
                <h4>🧠 Busca heurística experimental</h4>
                <p className="muted small">
                  Histórico local de hiperparâmetros testados; não é otimização Bayesiana
                  nem evidência para promoção de modelo.
                </p>
              </div>
              <button className="btn-small" onClick={loadBtStatus}>🔄 Atualizar</button>
            </div>

            {btMeta && btMeta.recent?.length > 0 && (
              <div className="table-scroll" style={{ marginTop: 12 }}>
                <p className="muted small">📊 {btMeta.total_records} registros no histórico do meta-learner</p>
                <table className="runs" style={{ marginTop: 8 }}>
                  <thead>
                    <tr>
                      <th>Liga</th><th>Feature</th><th>Window</th><th>HA</th><th>Rho</th>
                      <th>Accuracy</th><th>Brier</th><th>Data</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...btMeta.recent].reverse().slice(0, 20).map((h, i) => (
                      <tr key={i}>
                        <td>{h.league_id}</td>
                        <td>{h.feature}</td>
                        <td>{h.window}</td>
                        <td>{h.home_advantage?.toFixed(2)}</td>
                        <td>{h.rho?.toFixed(3)}</td>
                        <td>{h.accuracy?.toFixed(1)}%</td>
                        <td>{h.brier?.toFixed(4)}</td>
                        <td className="muted small">{h.timestamp?.slice(0, 16)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {btMeta && btMeta.recent?.length === 0 && (
              <p className="muted small" style={{ padding: '14px 0' }}>
                Nenhum registro ainda. Execute um ciclo de backtest para alimentar o meta-learner.
              </p>
            )}
          </section>

          {/* Histórico de ciclos */}
          <section className="panel">
            <div className="panel-head">
              <h4>📋 Histórico de ciclos</h4>
              <button className="btn-small" onClick={loadBtStatus}>🔄 Atualizar</button>
            </div>
            {btHistory?.history?.length > 0 ? (
              <div className="table-scroll" style={{ marginTop: 12 }}>
                <table className="runs">
                  <thead>
                    <tr><th>Data</th><th>Ligas</th><th>Sugestões</th><th>Status</th></tr>
                  </thead>
                  <tbody>
                    {[...btHistory.history].reverse().map((c, i) => (
                      <tr key={i}>
                        <td>{new Date(c.timestamp).toLocaleString()}</td>
                        <td>{c.leagues_processed}</td>
                        <td>{c.meta_suggestions}</td>
                        <td><span className="badge ok">concluído</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted small" style={{ padding: '14px 0' }}>
                Nenhum ciclo executado ainda. Clique em "Rodar ciclo agora" para iniciar.
              </p>
            )}
          </section>

          {/* Resumo Geral — Evolução/Propostas */}
          {btSummary && btSummary.leagues?.length > 0 && (
            <>
              <section className="panel">
                <div className="panel-head">
                  <div>
                    <h4>📈 Resumo Geral — Evolução vs Involução</h4>
                    <p className="muted small">
                      Comparação entre ciclos. 🟢 evolução · 🟡 estável · 🔴 involução.
                    </p>
                  </div>
                </div>

                <div className="hist-stats" style={{ marginTop: 12 }}>
                  <Stat label="Acurácia geral" value={`${btSummary.overall.accuracy}%`} ok={btSummary.overall.accuracy > 50} />
                  <Stat label="Brier geral" value={btSummary.overall.brier?.toFixed(4)} />
                  <Stat label="Acertos" value={btSummary.overall.correct} ok />
                  <Stat label="Erros" value={btSummary.overall.wrong} bad />
                  <Stat label="Ligas" value={btSummary.overall.leagues_count} />
                </div>

                <div className="hist-stats" style={{ marginTop: 8 }}>
                  <Stat label="🟢 Evoluíram" value={btSummary.overall.evolved} ok={btSummary.overall.evolved > 0} />
                  <Stat label="🟡 Estáveis" value={btSummary.overall.stable} />
                  <Stat label="🔴 Reverteram" value={btSummary.overall.involved} bad={btSummary.overall.involved > 0} />
                </div>

                <div className="table-scroll" style={{ marginTop: 14 }}>
                  <table className="runs">
                    <thead>
                      <tr>
                        <th>Trend</th>
                        <th>Liga</th>
                        <th>Accuracy</th>
                        <th>Δ Acc</th>
                        <th>Brier</th>
                        <th>Δ Brier</th>
                        <th>Acertos</th>
                        <th>Erros</th>
                        <th>% Erro</th>
                        <th>Promovido</th>
                      </tr>
                    </thead>
                    <tbody>
                      {btSummary.leagues.map((l, i) => {
                        const trendIcon = l.trend === 'evolution' ? '🟢' : l.trend === 'involution' ? '🔴' : '🟡'
                        const errorRate = l.total > 0 ? (l.wrong / l.total * 100).toFixed(1) : 0
                        return (
                          <tr key={i}>
                            <td style={{ fontSize: '1.2em' }}>{trendIcon}</td>
                            <td><b>{l.league_name}</b></td>
                            <td>{l.accuracy?.toFixed(1)}%</td>
                            <td style={{ color: l.delta_accuracy > 0 ? '#22c55e' : l.delta_accuracy < 0 ? '#ef4444' : '#94a3b8', fontWeight: 600 }}>
                              {l.delta_accuracy > 0 ? '+' : ''}{l.delta_accuracy?.toFixed(1)}%
                            </td>
                            <td>{l.brier?.toFixed(4)}</td>
                            <td style={{ color: l.delta_brier < 0 ? '#22c55e' : l.delta_brier > 0 ? '#ef4444' : '#94a3b8', fontWeight: 600 }}>
                              {l.delta_brier > 0 ? '+' : ''}{l.delta_brier?.toFixed(4)}
                            </td>
                            <td style={{ color: '#22c55e' }}>{l.correct}</td>
                            <td style={{ color: '#ef4444' }}>{l.wrong}</td>
                            <td style={{ color: errorRate > 55 ? '#ef4444' : errorRate < 45 ? '#22c55e' : '#94a3b8' }}>
                              {errorRate}%
                            </td>
                            <td>{l.promoted ? '✅' : '—'}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* Propostas de Apostas */}
              <section className="panel">
                <div className="panel-head">
                  <div>
                    <h4>🎯 Propostas de Apostas — Acurácia por Tipo</h4>
                    <p className="muted small">
                      Análise de acerto das propostas geradas pelo modelo em cada tipo de aposta.
                    </p>
                  </div>
                </div>

                <div className="hist-stats" style={{ marginTop: 12 }}>
                  {Object.entries(btSummary.proposals_summary || {}).map(([type, data]) => (
                    <Stat key={type}
                          label={type}
                          value={data.total > 0 ? `${data.accuracy}% (${data.correct}/${data.total})` : 'sem dados'}
                          ok={data.accuracy > 55}
                          bad={data.accuracy < 45 && data.total > 10} />
                  ))}
                </div>

                <div className="table-scroll" style={{ marginTop: 14 }}>
                  <table className="runs">
                    <thead>
                      <tr>
                        <th>Tipo</th>
                        <th>Total</th>
                        <th>Acertos</th>
                        <th>Erros</th>
                        <th>Acurácia</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(btSummary.proposals_summary || {}).map(([type, data]) => {
                        const status = data.accuracy >= 55 ? '🟢 Lucrativo' : data.accuracy >= 45 ? '🟡 Neutro' : '🔴 Prejuízo'
                        return (
                          <tr key={type}>
                            <td><b>{type}</b></td>
                            <td>{data.total}</td>
                            <td style={{ color: '#22c55e' }}>{data.correct}</td>
                            <td style={{ color: '#ef4444' }}>{data.total - data.correct}</td>
                            <td style={{ fontWeight: 600, color: data.accuracy > 55 ? '#22c55e' : data.accuracy < 45 ? '#ef4444' : '#94a3b8' }}>
                              {data.accuracy}%
                            </td>
                            <td>{status}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* Análise de Erros por Liga */}
              <section className="panel">
                <div className="panel-head">
                  <div>
                    <h4>❌ Análise de Erros por Resultado</h4>
                    <p className="muted small">
                      Distribuição dos erros: quando o modelo erra, qual resultado real aparece mais?
                    </p>
                  </div>
                </div>

                <div className="table-scroll" style={{ marginTop: 12 }}>
                  <table className="runs">
                    <thead>
                      <tr>
                        <th>Liga</th>
                        <th>Total</th>
                        <th>Erros</th>
                        <th>% Erro</th>
                        <th>Erros → Casa vence</th>
                        <th>Erros → Empate</th>
                        <th>Erros → Fora vence</th>
                        <th>Confiança Alta (certo)</th>
                        <th>Confiança Alta (errado)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {btSummary.leagues.filter(l => l.wrong > 0).map((l, i) => {
                        const err = l.error_analysis || {}
                        const bins = err.confidence_bins || {}
                        const highAcc = bins.high_correct || 0
                        const highWrong = bins.high_wrong || 0
                        return (
                          <tr key={i}>
                            <td><b>{l.league_name}</b></td>
                            <td>{l.total}</td>
                            <td style={{ color: '#ef4444' }}>{l.wrong}</td>
                            <td>{(l.wrong / l.total * 100).toFixed(1)}%</td>
                            <td>{err.errors_by_result?.['1'] || 0}</td>
                            <td>{err.errors_by_result?.['X'] || 0}</td>
                            <td>{err.errors_by_result?.['2'] || 0}</td>
                            <td style={{ color: '#22c55e' }}>{highAcc}</td>
                            <td style={{ color: '#ef4444' }}>{highWrong}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}
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

  // ticks dinâmicos: passo 25 para faixas largas, 10 para estreitas
  const step = (hiY - loY) > 60 ? 25 : 10
  const yTicks = []
  for (let t = Math.ceil(loY / step) * step; t <= hiY; t += step) yTicks.push(t)

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

function PredictionView({ p, token, onSave }) {
  const { match, lambdas, probs, top_scores, proposals, compare, model } = p
  const [picked, setPicked] = useState(null)
  const [chestOpen, setChestOpen] = useState(false)
  const [risk, setRisk] = useState(null)
  const [riskLoading, setRiskLoading] = useState(false)
  const [riskKelly, setRiskKelly] = useState(0.25)
  const [riskBankroll, setRiskBankroll] = useState(1000)

  const pickOptions = useMemo(() => {
    const opts = []
    const p1 = probs['1x2']
    const fav = Object.keys(p1).reduce((a, b) => p1[a] >= p1[b] ? a : b)
    const favName = fav === '1' ? match.home : fav === '2' ? match.away : 'Empate'
    opts.push({ type: '1X2', value: fav, label: `1X2: ${favName}`, prob: p1[fav] })
    for (const line of [1.5, 2.5]) {
      const ov = probs['over'][`over_${line}`]
      const un = probs['under'][`under_${line}`]
      if (ov >= un) opts.push({ type: 'GOLS', value: `over_${line}`, label: `Over ${line}`, prob: ov })
      else opts.push({ type: 'GOLS', value: `under_${line}`, label: `Under ${line}`, prob: un })
    }
    const btts = probs['btts']
    if (btts['sim'] >= 0.5) opts.push({ type: 'BTTS', value: 'sim', label: 'BTTS Sim', prob: btts['sim'] })
    else opts.push({ type: 'BTTS', value: 'nao', label: 'BTTS Não', prob: btts['nao'] })
    return opts
  }, [probs, match])

  useEffect(() => { setPicked(null); setRisk(null) }, [p])

  async function loadRisk() {
    if (!match.id) { alert('Previsão de confronto arbitrário — sem match_id para risco'); return }
    setRiskLoading(true)
    try {
      setRisk(await api.riskMatch(match.id, token, { kelly_fraction: riskKelly, bankroll: riskBankroll }))
    } catch (_e) { /* risco é opcional */ }
    setRiskLoading(false)
  }

  function save() {
    if (!picked) { alert('Escolha uma jogada para salvar'); return }
    const odd = picked.prob > 0 ? (1 / picked.prob).toFixed(2) : '—'
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

      <p className="experimental-notice">
        Experimental: probabilidades e mercados sao informativos, sem validacao
        temporal concluida ou garantia de desempenho.
      </p>

      {model && (model.accuracy != null || model.home_advantage) && (
        <div className="model-chip">
          🧠 modelo {match.league}: {model.feature || 'xg'} · HA {Number(model.home_advantage).toFixed(2)} · janela {model.window}
          {model.method && <> · {METHOD_META[model.method]?.icon} {METHOD_META[model.method]?.label || model.method}</>}
          {model.context && Object.values(model.context).some(Boolean) && <> · ctx {ctxChips(model.context)}</>}
          {model.accuracy != null && <> · acurácia {Number(model.accuracy).toFixed(1)}%</>}
          {model.brier != null && <> · Brier {Number(model.brier).toFixed(3)}</>}
        </div>
      )}

      {/* FASE 11 — Risk Engine Panel */}
      {match.id && (
        <div className="risk-panel">
          <div className="risk-header">
            <h4>🛡️ Gestão de Risco <span className="experimental-tag">experimental</span></h4>
            <div className="risk-controls">
              <label>
                Kelly
                <select value={riskKelly} onChange={e => setRiskKelly(Number(e.target.value))}>
                  <option value={0.125}>1/8 Kelly</option>
                  <option value={0.25}>1/4 Kelly</option>
                  <option value={0.5}>1/2 Kelly</option>
                  <option value={0.75}>3/4 Kelly</option>
                  <option value={1}>Full Kelly</option>
                </select>
              </label>
              <label>
                Banca
                <input type="number" value={riskBankroll} min={100} step={100}
                       onChange={e => setRiskBankroll(Number(e.target.value))}
                       style={{ width: 80 }} />
              </label>
              <button className="btn-small" onClick={loadRisk} disabled={riskLoading}>
                {riskLoading ? 'Calculando...' : '📊 Calcular risco'}
              </button>
            </div>
          </div>

          {risk && (
            <div className="risk-body">
              <div className="hist-stats">
                <Stat label="Sinais" value={risk.summary.total_signals} ok={risk.summary.any_value} />
                <Stat label="Stake sugerida" value={`${risk.summary.total_stake_suggested} u`} />
                <Stat label="Exposição" value={`${risk.summary.total_exposure_pct}%`} />
                <Stat label="Mercado externo" value={risk.market.market_available ? 'Disponível' : 'Indisponível'} />
              </div>
              {risk.market.market_quote && (
                <p className="muted small" style={{ marginTop: 8 }}>
                  Quote externa: {risk.market.market_quote.provider} · capturada em {risk.market.market_quote.captured_at}
                </p>
              )}

              {risk.signals.length > 0 && (
                <div className="table-scroll" style={{ marginTop: 10 }}>
                  <table className="runs">
                    <thead>
                      <tr>
                        <th>Jogada</th>
                        <th>Prob.</th>
                         <th>Odd justa do modelo</th>
                         <th>Odd externa</th>
                         <th>EV esperado</th>
                        <th>Kelly</th>
                        <th>Stake</th>
                        <th>Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {risk.signals.map((s, i) => (
                        <tr key={i}>
                          <td><b>{s.label}</b></td>
                          <td>{(s.prob * 100).toFixed(1)}%</td>
                          <td>@{s.fair_odds}</td>
                          <td>@{s.market_odds}</td>
                          <td style={{ color: s.edge > 0 ? '#34d399' : '#f87171' }}>
                            {s.edge > 0 ? '+' : ''}{(s.edge * 100).toFixed(1)}%
                          </td>
                          <td>{(s.kelly_adjusted * 100).toFixed(2)}%</td>
                          <td>{s.stake_suggested} u</td>
                          <td>
                            <span className={`badge risk-${s.risk_score.grade.toLowerCase()}`}>
                              {s.risk_score.grade} · {s.risk_score.score}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {risk.signals.length === 0 && (
                <p className="muted small" style={{ marginTop: 8 }}>
                  Odds externas não foram integradas. Fair odds são apenas referência
                  do modelo e não geram edge, Kelly ou recomendação de aposta.
                </p>
              )}

              <p className="muted small" style={{ marginTop: 8 }}>
                ⚠️ Kelly fracionado: {risk.config.kelly_label} ·
                Max stake: {risk.config.max_stake} u ·
                Max exposição/jogo: {risk.config.max_exposure_per_match} u ·
                Max diário: {risk.config.max_daily_exposure} u
              </p>
            </div>
          )}

          {!risk && !riskLoading && (
            <p className="muted small" style={{ marginTop: 6 }}>
              Simulação informativa: não use como recomendação de aposta ou garantia de retorno.
            </p>
          )}
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
                 <div className="bar-val">{(v * 100).toFixed(1)}% <span className="odd">Justa @{probs['odds_1x2'][k]}</span></div>
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
                 <div className="bar-val">{(ov * 100).toFixed(1)}% <span className="odd">Justa @{ov > 0 ? (1 / ov).toFixed(2) : '—'}</span>
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
              <span className="odd">Justa @{probs['btts']['sim'] > 0 ? (1 / probs['btts']['sim']).toFixed(2) : '—'}</span></div>
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
              <span className="odd">Justa @{s.odd}</span>
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
                {o.label} ({(o.prob * 100).toFixed(1)}%)
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
