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
  const [batch, setBatch] = useState(null)
  const [batchTimer, setBatchTimer] = useState(null)
  const [learn, setLearn] = useState(null)
  const [cal, setCal] = useState(null)
  const [calTimer, setCalTimer] = useState(null)
  const [backtest, setBacktest] = useState(null)
  const [backtesting, setBacktesting] = useState(false)
  const [dataOv, setDataOv] = useState([])
  const [dataFilter, setDataFilter] = useState('')

  async function refreshLeagues() {
    setLeagues(await api.leagues(token))
  }

  useEffect(() => {
    refreshLeagues().catch(e => setError(e.message))
    loadRuns()
    if (tab === 'historico') loadHistory()
    if (tab === 'aprendizado') loadLearning()
    if (tab === 'dados') loadDataOverview()
  }, [tab])

  useEffect(() => () => clearInterval(batchTimer), [batchTimer])
  useEffect(() => () => clearInterval(calTimer), [calTimer])

  async function loadRuns() {
    try { setRuns(await api.runs(token)) } catch {}
  }

  async function loadHistory() {
    try { setHist(await api.predictions(token)) } catch (e) { setError(e.message) }
  }

  async function loadLearning() {
    try { setLearn(await api.learningStatus(token)) } catch (e) { setError(e.message) }
  }

  async function loadDataOverview() {
    try { setDataOv(await api.dataOverview(token)) } catch (e) { setError(e.message) }
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

  async function startBatch() {
    setLoading(true); setError('')
    try {
      const st = await api.scrapeBatch(token)
      setBatch(st)
      clearInterval(batchTimer)
      const t = setInterval(async () => {
        try {
          const s = await api.scrapeBatchStatus(token)
          setBatch(s)
          if (!s.running) {
            clearInterval(t); setBatchTimer(null)
            refreshLeagues()
            loadRuns()
            if (s.auto_calibrate && s.ok > 0) watchCalibration()
          }
        } catch {}
      }, 3000)
      setBatchTimer(t)
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  async function watchCalibration() {
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

  const groupedByCountry = useMemo(() => {
    const groups = {}
    for (const l of filteredLeagues) {
      const key = l.country || 'Outros'
      if (!groups[key]) groups[key] = []
      groups[key].push(l)
    }
    return Object.entries(groups).sort((a, b) => a[0].localeCompare(b[0]))
  }, [filteredLeagues])

  const selLeagueObj = selLeague ? leagues.find(l => l.id === selLeague) : null

  return (
    <div className="app">
      <header>
        <div className="brand">⚽ AP2WEB</div>
        <nav>
          <button className={tab === 'confronto' ? 'active' : ''} onClick={() => setTab('confronto')}>Confronto</button>
          <button className={tab === 'liga' ? 'active' : ''} onClick={() => setTab('liga')}>Ligas</button>
          <button className={tab === 'historico' ? 'active' : ''} onClick={() => setTab('historico')}>Histórico</button>
          <button className={tab === 'aprendizado' ? 'active' : ''} onClick={() => setTab('aprendizado')}>Aprendizado</button>
          <button className={tab === 'dados' ? 'active' : ''} onClick={() => setTab('dados')}>Dados</button>
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
            <h3>Ligas no banco <span className="muted small">({leagues.length})</span></h3>
            <input className="search" placeholder="🔎 Buscar liga ou país..."
                   value={leagueSearch} onChange={e => setLeagueSearch(e.target.value)} />
            {filteredLeagues.length === 0 && <p className="muted">Nenhuma liga. Rape uma liga ou os jogos de hoje.</p>}
            {groupedByCountry.map(([country, list]) => (
              <div key={country} className="league-group">
                <div className="league-group-title">{flag(country)} {country} <span className="muted small">({list.length})</span></div>
                <ul className="league-list">
                  {list.map(l => (
                    <li key={l.id} className={selLeague === l.id ? 'active' : ''} onClick={() => selectLeague(l.id)}>
                      <span className="name">{l.name}</span>
                      <span className="meta">{l.matches} jogos · {l.scheduled} agendados</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
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
                      <tr><th>Liga</th><th>HA</th><th>Janela</th><th>Acurácia</th><th>Brier</th><th>Amostras</th><th>Calibrada</th><th></th></tr>
                    </thead>
                    <tbody>
                      {[...learn.calibrated]
                        .sort((a, b) => (b.accuracy || 0) - (a.accuracy || 0))
                        .map(lm => (
                          <tr key={lm.league_id}>
                            <td><b>{lm.name}</b></td>
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
                <p className="muted small">Reavaliação com o modelo padrão (HA 1.15, janela 10).</p>
              </div>
            )}
          </section>
        </main>
      )}

      {tab === 'dados' && (
        <main className="column">
          <section className="panel">
            <div className="panel-head">
              <div>
                <h3>🗄️ Dados utilizados na análise</h3>
                <p className="muted small">Visão geral por liga: quantos jogos estão no banco, se há dados corrompidos, quando foi a última partida registrada e o estado do modelo calibrado.</p>
              </div>
              <button className="btn-small" onClick={loadDataOverview}>🔄 Atualizar</button>
            </div>
            <input className="search" placeholder="Buscar liga..." value={dataFilter}
                   onChange={e => setDataFilter(e.target.value)} style={{ marginBottom: 12 }} />
            <div className="table-scroll">
              <table className="runs">
                <thead>
                  <tr><th>Liga</th><th>Jogados</th><th>Agendados</th><th>Dados limpos</th><th>Corrompidos</th><th>Stats</th><th>Última partida</th><th>Modelo</th><th>HA</th><th>Jan</th><th>Acur.</th></tr>
                </thead>
                <tbody>
                  {dataOv
                    .filter(r => !dataFilter.trim() || r.name.toLowerCase().includes(dataFilter.trim().toLowerCase()))
                    .map(r => (
                      <tr key={r.id}>
                        <td><b>{r.name}</b></td>
                        <td>{r.played}</td>
                        <td>{r.scheduled}</td>
                        <td>{r.clean}</td>
                        <td>{r.corrupt > 0 ? <span style={{ color: '#f87171' }}>{r.corrupt} ⚠️</span> : <span style={{ color: '#4ade80' }}>0 ✓</span>}</td>
                        <td>{r.stats_rows}</td>
                        <td>{r.last_played || '—'}</td>
                        <td>{r.has_model ? '✅' : '—'}</td>
                        <td>{r.home_advantage != null ? Number(r.home_advantage).toFixed(2) : '—'}</td>
                        <td>{r.window || '—'}</td>
                        <td>{r.accuracy ? `${r.accuracy.toFixed(1)}%` : '—'}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
            <p className="muted small" style={{ marginTop: 10 }}>
              Corrompidos = placares impossíveis (ex.: horários virando placar). Agora o parser ignora jogos futuros; se aparecer ⚠️, rode a raspagem para limpar.
            </p>
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
              <button className="btn-primary btn-green" onClick={startBatch} disabled={loading || (batch && batch.running)}>
                {batch && batch.running ? `Raspando ${batch.done}/${batch.total}...` : '⚡ Raspar TODAS as ligas'}
              </button>
              <span className="muted small">Raspa os resultados (FT/HT) de todas as {batch?.total || 49} ligas da lista.</span>
            </div>

            {batch && batch.running && (
              <div className="batch-progress">
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${batch.total ? (batch.done / batch.total) * 100 : 0}%` }} />
                </div>
                <p className="muted small">
                  {batch.done}/{batch.total} ligas · {batch.ok} ok · {batch.fail} falhas
                  {batch.current ? ` · agora: ${batch.current}` : ''}
                </p>
              </div>
            )}

            {batch && !batch.running && batch.finished_at && (
              <p className="muted small">
                ✅ Última raspagem em lote: {batch.ok} ligas ok, {batch.fail} falhas.
                {batch.errors?.length > 0 && <> Falhas: {batch.errors.map(e => e.league).join(', ')}</>}
              </p>
            )}

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

function NeuralNet({ learn, cal }) {
  const running = cal?.running || false
  const total = learn?.calibrated?.length || 0
  const acc = total ? learn.calibrated.reduce((s, m) => s + (m.accuracy || 0), 0) / total : 0
  const grid = learn?.grid?.home_advantage?.length || 7
  const layers = [grid, Math.max(8, Math.min(16, Math.round(total / 4))), 3]
  const xs = [70, 190, 310]
  const cols = ['#22d3ee', '#4ade80', '#a78bfa']
  const ys = []
  layers.forEach((n, li) => {
    const arr = []
    for (let i = 0; i < n; i++) arr.push(40 + (220 / (n - 1 || 1)) * i)
    ys.push(arr)
  })
  const edges = []
  for (let l = 0; l < 2; l++) {
    ys[l].forEach((a, i) => {
      ys[l + 1].forEach((b, j) => {
        edges.push({ x1: xs[l], y1: a, x2: xs[l + 1], y2: b, k: (i + j) % 5 })
      })
    })
  }
  const nodes = []
  for (let l = 0; l < 3; l++) {
    ys[l].forEach((y, i) => {
      const active = running || (l === 0 ? i < grid : l === 1 ? i < Math.ceil(total / 4) : i < 2)
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
        <text x="70" y="292" textAnchor="middle" fill="#94a3b8" fontSize="11">entrada</text>
        <text x="190" y="292" textAnchor="middle" fill="#94a3b8" fontSize="11">oculta</text>
        <text x="310" y="292" textAnchor="middle" fill="#94a3b8" fontSize="11">saída</text>
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
          🧠 modelo {match.league}: HA {Number(model.home_advantage).toFixed(2)} · janela {model.window}
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
                  <p className="muted small">Fonte: {p.data.source === 'team_stats' ? 'team_stats (stats por time do soccerstats)' : 'placares jogados (cálculo local)'} · janela {p.data.model.window} · HA {Number(p.data.model.home_advantage).toFixed(2)}</p>
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
                        <tr key={i}><td>{g.match_date}</td><td>{g.home}</td><td>{g.away}</td><td>{g.ft_home}-{g.ft_away}</td></tr>
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
                    HA {Number(p.data.model.home_advantage).toFixed(2)} · janela {p.data.model.window}
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