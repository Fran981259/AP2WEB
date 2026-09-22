import PredictionView from '../../prediction/PredictionView.jsx'
import { flag } from '../../../utils/flags.js'

export default function ConfrontoTab({ d, token, canOperate, operationHint }) {
  return (
    <main>
      {d.showMethodNotice && (
        <div className="muted small mb-12">
          Motor experimental: probabilidades e odds justas sao informativas. Mercado, EV e Kelly exigem quote externa timestampada.
          <button className="btn-link" onClick={() => d.setShowMethodNotice(false)}>Ocultar</button>
        </div>
      )}
      <aside>
        <h3>Ligas no banco <span className="muted small">({d.leagues.length})</span></h3>
        <input className="search" placeholder="🔎 Buscar liga ou país..."
               value={d.leagueSearch} onChange={e => d.setLeagueSearch(e.target.value)} />
        {d.filteredLeagues.length === 0 && <p className="muted">
          {canOperate
            ? 'Nenhuma liga. Sincronize uma liga na aba Sofascore.'
            : 'Nenhuma liga sincronizada. Peça a um operador para iniciar a sincronização.'}
        </p>}
        {d.groupedByContinent.map(([continentName, list]) => {
          const open = d.openConts.has(continentName)
          return (
            <div key={continentName} className="league-group continent">
              <button className="continent-toggle" onClick={() => d.toggleCont(continentName)}>
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
                          <li key={l.id} className={d.selLeague === l.id ? 'active' : ''} onClick={() => d.selectLeague(l.id)}>
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
              <select value={d.cfLeague} onChange={e => d.onCfLeagueChange(e.target.value)}>
                <option value="">— selecione —</option>
                {d.leagues.map(l => (
                  <option key={l.id} value={l.id}>
                    {flag(l.country)} {l.name} ({l.played} jogos)
                  </option>
                ))}
              </select>
            </label>
            <button className="btn-small btn-demand" onClick={d.onCfDemand} disabled={!canOperate || d.loading || !d.cfLeague}
                    title={operationHint || 'Sincronizar esta liga no Sofascore'}>
              {d.loading ? 'Sincronizando...' : '📥 Sincronizar dados'}
            </button>
          </div>
          {d.cfLeague && (
            <div className="cf-form">
              <label>
                Time da casa
                <select value={d.cfHome} onChange={e => d.setCfHome(e.target.value)}>
                  <option value="">— selecione —</option>
                  {d.cfTeams.map(t => (
                    <option key={t.id} value={t.id} disabled={t.id === Number(d.cfAway)}>
                      {t.name} {t.games_played > 0 ? `(${t.games_played} jogos)` : ''}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Time visitante
                <select value={d.cfAway} onChange={e => d.setCfAway(e.target.value)}>
                  <option value="">— selecione —</option>
                  {d.cfTeams.map(t => (
                    <option key={t.id} value={t.id} disabled={t.id === Number(d.cfHome)}>
                      {t.name} {t.games_played > 0 ? `(${t.games_played} jogos)` : ''}
                    </option>
                  ))}
                </select>
              </label>
              <button className="btn-primary" onClick={d.onCfPredict} disabled={d.loading || !d.cfHome || !d.cfAway}>
                {d.loading ? 'Prevendo...' : '🔮 Prever confronto'}
              </button>
            </div>
          )}

          {d.cfLeague && d.cfTeams.length === 0 && !d.loading && (
            <p className="muted small">Nenhum time nesta liga ainda. Use "Sincronizar dados" para puxar os jogos do Sofascore.</p>
          )}
        </section>

        {d.prediction && (
          <PredictionView p={d.prediction} token={token} onSave={d.onSavePrediction} />
        )}

        {d.selLeague && d.selLeagueObj && (
          <section className="panel">
            <h3>{flag(d.selLeagueObj.country)} {d.selLeagueObj.name} — Partidas</h3>
            <div className="table-scroll">
              <table className="matches">
                <thead>
                  <tr><th>Data</th><th>Casa</th><th>Placar</th><th>Fora</th><th></th></tr>
                </thead>
                <tbody>
                  {d.matches.map(m => (
                    <tr key={m.id}>
                      <td>{m.match_date}</td>
                      <td>{m.home}</td>
                      <td>{m.status === 'played' ? `${m.score_home} - ${m.score_away}` : '—'}</td>
                      <td>{m.away}</td>
                      <td>
                        <button className="btn-small" onClick={() => d.openPrediction(m.id)} disabled={d.loading}>
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
  )
}
