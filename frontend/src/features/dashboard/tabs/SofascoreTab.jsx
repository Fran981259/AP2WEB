import { STAT_LABELS } from '../../../utils/methodMeta.js'
import { flag } from '../../../utils/flags.js'

export default function SofascoreTab({ d, canOperate, operationHint }) {
  const { sofa, sofaStatus, sofaLeague, sofaSelFields, sofaTeamFilter } = d
  const running = ['pending', 'running'].includes(sofaStatus?.status)
  return (
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
                d.setSofaLeague(v)
                d.loadSofa(v || undefined)
              }}>
                <option value="">Todas</option>
                {d.leagues.map(l => (
                  <option key={l.id} value={l.id}>{flag(l.country)} {l.name}</option>
                ))}
              </select>
            </label>
            {sofaLeague && (
              <button className="btn-primary" onClick={() => d.startSofaSync(sofaLeague)}
                      disabled={!canOperate || d.loading || running} title={operationHint}>
                📥 Sync liga
              </button>
            )}
            <button className="btn-primary" onClick={() => d.startSofaSync()}
                    disabled={!canOperate || d.loading || running} title={operationHint}>
              {running ? `Sincronizando ${Math.round((sofaStatus.progress || 0) * 100)}%...` : '📥 Sincronizar tudo'}
            </button>
          </div>
        </div>

        {running && (
          <div className="batch-progress">
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${(sofaStatus.progress || 0) * 100}%` }} />
            </div>
            <p className="muted small">{Math.round((sofaStatus.progress || 0) * 100)}%{sofaStatus.detail ? ` · ${sofaStatus.detail}` : ''}</p>
          </div>
        )}
        {sofaStatus && !running && sofaStatus.error_message && (
          <p className="error mt-8">✕ {sofaStatus.error_message}</p>
        )}
        {sofaStatus && !running && sofaStatus.finished_at && sofaStatus.result?.errors?.length > 0 && (
          <p className="muted small mt-8 text-warn">
            ⚠️ Liga(s) com falha: {sofaStatus.result.errors.map(e => e.league).join(', ')}
          </p>
        )}
        {sofa && sofa.length > 0 && (
          <p className="muted small mt-8">
            ✅ {sofa.length} jogos da próxima rodada
            {sofaStatus?.finished_at ? ` · sincronizado em ${sofaStatus.finished_at}` : ''}
          </p>
        )}

        {sofa && sofa.length > 0 && (
          <>
            <div className="cf-form flex-wrap mt-10">
              <label>
                Time
                <input className="search w-180" placeholder="Buscar time..."
                       value={sofaTeamFilter} onChange={e => d.setSofaTeamFilter(e.target.value)} />
              </label>
              <label>
                Métricas
                <select multiple size={6} className="select-multi" value={sofaSelFields}
                        onChange={e => {
                          const v = [...e.target.options].filter(o => o.selected).map(o => o.value)
                          d.setSofaSelFields(v)
                        }}>
                  {Object.entries(STAT_LABELS).map(([k, label]) => (
                    <option key={k} value={k}>{label}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className="table-scroll mt-12">
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

        {(!sofa || sofa.length === 0) && !running && (
          <p className="muted small pad-y-14">
            Nenhum dado ainda. Clique em "Sincronizar tudo" para puxar os jogos de todas as ligas do Sofascore.
          </p>
        )}
      </section>
    </main>
  )
}
