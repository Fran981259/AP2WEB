const API = '/api'

// Phase 2: sessão via cookies HttpOnly (ap2web_token / ap2web_refresh) + CSRF
// double-submit (ap2web_csrf). O token já não é persistido em localStorage —
// fica somente no cookie, reduzindo a superfície de XSS.
const CSRF_COOKIE = 'ap2web_csrf'

// Callback registrado pelo App para transicionar à tela de login quando a
// sessão expira de forma irrecuperável (refresh falhou).
let _onUnauthorized = null
export function setOnUnauthorized(fn) {
  _onUnauthorized = fn
}

let _refreshing = null

function getCookie(name) {
  const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return m ? decodeURIComponent(m[1]) : null
}

// ── helpers: error mapping + abort/timeout ──────────────────

function httpErrorMessage(status, detail) {
  switch (status) {
    case 401: return detail || 'Sessão expirada — faça login novamente'
    case 403: return detail || 'Permissão negada para esta operação'
    case 409: return detail || 'Conflito — recurso já existe ou job em andamento'
    case 429: return detail || 'Muitas requisições — aguarde e tente novamente'
    default:
      if (status >= 500) return detail || `Erro no servidor (${status}) — tente novamente`
      return detail || `Erro ${status}`
  }
}

// Refresh rotação em background (cookie-based). Sincronizado para evitar
// rajadas concorrentes.
async function refreshSession() {
  if (_refreshing) return _refreshing
  _refreshing = (async () => {
    const res = await fetch(API + '/auth/refresh', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': getCookie(CSRF_COOKIE) || '',
      },
      body: '{}',
    })
    return res.ok
  })().finally(() => {
    _refreshing = null
  })
  return _refreshing
}

let _reqSeq = 0

export const api = {
  async request(path, { method = 'GET', body, token, signal, timeout = 15000 } = {},
                _retried = false) {
    const controller = new AbortController()
    const timeoutId = timeout ? setTimeout(() => controller.abort(), timeout) : null
    // compor sinal externo + timeout interno
    const combinedSignal = signal
      ? (() => {
          const ac = new AbortController()
          const onAbort = () => ac.abort()
          signal.addEventListener('abort', onAbort, { once: true })
          controller.signal.addEventListener('abort', () => {
            ac.abort()
            signal.removeEventListener('abort', onAbort)
          })
          // timeout também aborta o combinado
          controller.signal.addEventListener('abort', () => ac.abort(), { once: true })
          return ac.signal
        })()
      : controller.signal

    const seq = ++_reqSeq
    const unsafe = !['GET', 'HEAD', 'OPTIONS'].includes(method)
    const csrf = unsafe ? getCookie(CSRF_COOKIE) : null
    try {
      const res = await fetch(API + path, {
        method,
        credentials: 'include', // enviamos cookies de sessão sempre
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(unsafe && csrf ? { 'X-CSRF-Token': csrf } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: combinedSignal,
      })
      if (timeoutId) clearTimeout(timeoutId)

      // Sessão expirada: tenta refresh (rotação) uma vez e repete.
      if (res.status === 401 && !_retried && !path.startsWith('/auth/')) {
        const refreshed = await refreshSession()
        if (refreshed) {
          if (timeout) clearTimeout(timeoutId)
          return this.request(path, { method, body, token, signal, timeout }, true)
        }
        if (_onUnauthorized) _onUnauthorized()
        throw new Error(httpErrorMessage(401, 'Sessão expirada — faça login novamente'))
      }
      if (res.status === 204) return {}
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        const msg = httpErrorMessage(res.status, data.detail)
        const err = new Error(msg)
        err.status = res.status
        err.detail = data.detail
        err.seq = seq
        throw err
      }
      // anexar seq para controle de staleness no caller (se quiser)
      if (data && typeof data === 'object') data._reqSeq = seq
      return data
    } catch (err) {
      if (timeoutId) clearTimeout(timeoutId)
      if (err.name === 'AbortError') {
        const aborted = new Error('Requisição cancelada ou timeout')
        aborted.status = 0
        aborted.aborted = true
        throw aborted
      }
      throw err
    }
  },
  // Util: criar AbortController para caller gerenciar polling/cancelamento
  abortController() {
    return new AbortController()
  },
  login(username, password, opts = {}) {
    return this.request('/login', { method: 'POST', body: { username, password }, ...opts })
  },
  register(username, password, opts = {}) {
    return this.request('/register', { method: 'POST', body: { username, password }, ...opts })
  },
  logout(opts = {}) {
    return this.request('/logout', { method: 'POST', body: {}, ...opts })
  },
  me(opts = {}) {
    return this.request('/me', { ...opts })
  },
  leagues(token, opts = {}) { return this.request('/leagues', { token, ...opts }) },
  job(jobId, token, opts = {}) { return this.request(`/jobs/${jobId}`, { token, ...opts }) },
  cancelJob(jobId, token, opts = {}) { return this.request(`/jobs/${jobId}/cancel`, { method: 'POST', body: {}, token, ...opts }) },
  leagueMatches(id, token, opts = {}) { return this.request(`/leagues/${id}/matches`, { token, ...opts }) },
  leagueTeams(id, token, opts = {}) { return this.request(`/leagues/${id}/teams`, { token, ...opts }) },
  prediction(id, token, opts = {}) { return this.request(`/matches/${id}/prediction`, { token, ...opts }) },
  predictFixture(leagueId, homeId, awayId, token, opts = {}) {
    return this.request('/predict/fixture', {
      method: 'POST', token,
      body: { league_id: leagueId, home_team_id: homeId, away_team_id: awayId }, ...opts
    })
  },
  learningStatus(token, opts = {}) { return this.request('/learning/status', { token, ...opts }) },
  learningCalibrate(token, opts = {}) { return this.request('/learning/calibrate', { method: 'POST', body: {}, token, ...opts }) },
  learningBacktest(leagueId, token, opts = {}) { return this.request(`/learning/backtest/${leagueId}`, { token, ...opts }) },
  learningCurve(token, opts = {}) { return this.request('/learning/curve', { token, ...opts }) },
  predictions(token, opts = {}) { return this.request('/predictions', { token, ...opts }) },
  savePrediction(data, token, opts = {}) { return this.request('/predictions', { method: 'POST', body: data, token, ...opts }) },
  deletePrediction(id, token, opts = {}) { return this.request(`/predictions/${id}`, { method: 'DELETE', token, ...opts }) },
  sofascoreSync(token, opts = {}) { return this.request('/sofascore/sync', { method: 'POST', body: {}, token, ...opts }) },
  sofascoreSyncLeague(leagueId, token, opts = {}) { return this.request(`/sofascore/sync/league/${leagueId}`, { method: 'POST', body: {}, token, ...opts }) },
  sofascoreData(leagueId, token, opts = {}) {
    const qs = `?next_round=1${leagueId ? `&league_id=${leagueId}` : ''}`
    return this.request(`/sofascore/data${qs}`, { token, ...opts })
  },
  evolutionSnapshot(token, opts = {}) { return this.request('/evolution/snapshot', { token, ...opts }) },
  evolutionHistory(limit = 50, token, opts = {}) {
    return this.request(`/evolution/history?limit=${limit}`, { token, ...opts })
  },
  // Backtest Engine
  backtestStart(intervalHours = 6, token, opts = {}) {
    return this.request(`/backtest/start?interval_hours=${intervalHours}`, { method: 'POST', body: {}, token, ...opts })
  },
  backtestStop(token, opts = {}) { return this.request('/backtest/stop', { method: 'POST', body: {}, token, ...opts }) },
  backtestStatus(token, opts = {}) { return this.request('/backtest/status', { token, ...opts }) },
  backtestRun(leagueIds = null, token, opts = {}) {
    return this.request('/backtest/run', {
      method: 'POST', token,
      body: leagueIds || [], ...opts
    })
  },
  backtestCV(leagueId, nFolds = 5, token, opts = {}) {
    return this.request(`/backtest/cv/${leagueId}?n_folds=${nFolds}`, { token, ...opts })
  },
  backtestHistory(limit = 20, token, opts = {}) {
    return this.request(`/backtest/history?limit=${limit}`, { token, ...opts })
  },
  backtestMeta(token, opts = {}) { return this.request('/backtest/meta', { token, ...opts }) },
  backtestSummary(token, opts = {}) { return this.request('/backtest/summary', { token, ...opts }) },
  // FASE 11 — Risk Engine
  riskMatch(matchId, token, params = {}, opts = {}) {
    const qs = new URLSearchParams(params).toString()
    return this.request(`/risk/${matchId}${qs ? '?' + qs : ''}`, { token, ...opts })
  },
  riskLeague(leagueId, token, params = {}, opts = {}) {
    const qs = new URLSearchParams(params).toString()
    return this.request(`/risk/league/${leagueId}${qs ? '?' + qs : ''}`, { token, ...opts })
  },
}
