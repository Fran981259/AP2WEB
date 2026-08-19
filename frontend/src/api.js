const API = '/api'

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
  scrapeToday(token) { return this.request('/scrape/today', { method: 'POST', token }) },
  scrapeLeague(code, token) { return this.request('/scrape/league', { method: 'POST', body: { league: code }, token }) },
  runs(token) { return this.request('/runs', { token }) }
}
