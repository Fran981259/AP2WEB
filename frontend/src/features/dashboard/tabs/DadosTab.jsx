import { flag } from '../../../utils/flags.js'
import { ctxChips, methodBadge } from '../../../utils/badges.jsx'

export default function DadosTab({ d }) {
  const { leagues, learn, dataQuality } = d
  return (
    <main className="column">
      <section className="panel">
        <div className="panel-head">
          <div>
            <h3>🗄️ Dados no banco</h3>
            <p className="muted small">Ligas sincronizadas do Sofascore: jogos jogados/agendados, temporada ativa, último sync e estado do modelo calibrado.</p>
          </div>
          <button className="btn-small" onClick={() => { d.refreshLeagues(); d.loadLearning(); d.loadDataQuality() }}>🔄 Atualizar</button>
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
        <div className="panel mt-16">
          <div className="panel-head">
            <div>
              <h3>🧪 Qualidade dos dados</h3>
              <p className="muted small">Gate operacional: resultados completos, cobertura de xG, histórico mínimo e sync recente. “Apta” não é promessa de acerto.</p>
            </div>
            <span className="muted small">{dataQuality ? `${dataQuality.summary.ready}/${dataQuality.summary.total} aptas` : 'Carregando...'}</span>
          </div>
          <div className="table-scroll">
            <table className="runs">
              <thead><tr><th>Liga</th><th>Estado</th><th>Jogos</th><th>Resultados</th><th>xG</th><th>Último sync</th><th>Diagnóstico</th></tr></thead>
              <tbody>
                {(dataQuality?.items || []).map(item => (
                  <tr key={item.league_id}>
                    <td><b>{item.name}</b></td><td>{item.status === 'ready' ? '✓ Apta' : item.status}</td>
                    <td>{item.played}</td><td>{(item.results_coverage * 100).toFixed(0)}%</td>
                    <td>{(item.xg_coverage * 100).toFixed(0)}%</td><td>{item.last_sync || '—'}</td><td className="muted small">{item.reason}</td>
                  </tr>
                ))}
                {dataQuality && dataQuality.items.length === 0 && <tr><td colSpan={7} className="muted">Nenhuma liga disponível.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </main>
  )
}
