const API = '/api'
const TOKEN_KEY = 'ap2web_token'
const USER_KEY = 'ap2web_user'

export const api = {
  async request(path, { method = 'GET', body, token } = {}) {
    const res = await fetch(API + path, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: body ? JSON.stringify(body) : undefined
    })
    if (res.status === 401 && token) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      window.location.reload()
      throw new Error('Sessão expirada')
    }
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || `Erro ${res.status}`)
    return data
  },
  login(username, password) {
    return this.request('/login', { method: 'POST', body: { username, password } })
  },
  register(username, password) {
    return this.request('/register', { method: 'POST', body: { username, password } })
  },
  leagues(token) { return this.request('/leagues', { token }) },
  leagueMatches(id, token) { return this.request(`/leagues/${id}/matches`, { token }) },
  leagueTeams(id, token) { return this.request(`/leagues/${id}/teams`, { token }) },
  prediction(id, token) { return this.request(`/matches/${id}/prediction`, { token }) },
  predictFixture(leagueId, homeId, awayId, token) {
    return this.request('/predict/fixture', {
      method: 'POST', token,
      body: { league_id: leagueId, home_team_id: homeId, away_team_id: awayId }
    })
  },
  learningStatus(token) { return this.request('/learning/status', { token }) },
  learningCalibrate(token) { return this.request('/learning/calibrate', { method: 'POST', body: {}, token }) },
  learningCalibrateStatus(token) { return this.request('/learning/calibrate/status', { token }) },
  learningBacktest(leagueId, token) { return this.request(`/learning/backtest/${leagueId}`, { token }) },
  learningCurve(token) { return this.request('/learning/curve', { token }) },
  predictions(token) { return this.request('/predictions', { token }) },
  savePrediction(data, token) { return this.request('/predictions', { method: 'POST', body: data, token }) },
  deletePrediction(id, token) { return this.request(`/predictions/${id}`, { method: 'DELETE', token }) },
  sofascoreSync(token) { return this.request('/sofascore/sync', { method: 'POST', body: {}, token }) },
  sofascoreSyncLeague(leagueId, token) { return this.request(`/sofascore/sync/league/${leagueId}`, { method: 'POST', body: {}, token }) },
  sofascoreStatus(token) { return this.request('/sofascore/status', { token }) },
  sofascoreData(leagueId, token) {
    const qs = leagueId ? `?league_id=${leagueId}` : ''
    return this.request(`/sofascore/data${qs}`, { token })
  },
  evolutionSnapshot(token) { return this.request('/evolution/snapshot', { token }) },
  evolutionHistory(limit = 50, token) {
    return this.request(`/evolution/history?limit=${limit}`, { token })
  },
  // Backtest Engine
  backtestStart(intervalHours = 6, token) {
    return this.request(`/backtest/start?interval_hours=${intervalHours}`, { method: 'POST', body: {}, token })
  },
  backtestStop(token) { return this.request('/backtest/stop', { method: 'POST', body: {}, token }) },
  backtestStatus(token) { return this.request('/backtest/status', { token }) },
  backtestRun(leagueIds = null, token) {
    return this.request('/backtest/run', {
      method: 'POST', token,
      body: leagueIds || []
    })
  },
  backtestCV(leagueId, nFolds = 5, token) {
    return this.request(`/backtest/cv/${leagueId}?n_folds=${nFolds}`, { token })
  },
  backtestHistory(limit = 20, token) {
    return this.request(`/backtest/history?limit=${limit}`, { token })
  },
  backtestMeta(token) { return this.request('/backtest/meta', { token }) },
  backtestSummary(token) { return this.request('/backtest/summary', { token }) },
  // FASE 11 — Risk Engine
  riskMatch(matchId, token, params = {}) {
    const qs = new URLSearchParams(params).toString()
    return this.request(`/risk/${matchId}${qs ? '?' + qs : ''}`, { token })
  },
  riskLeague(leagueId, token, params = {}) {
    const qs = new URLSearchParams(params).toString()
    return this.request(`/risk/league/${leagueId}${qs ? '?' + qs : ''}`, { token })
  },
}