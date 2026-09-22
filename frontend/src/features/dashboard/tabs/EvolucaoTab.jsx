import LineChart from '../../../components/LineChart.jsx'
import Stat from '../../../components/Stat.jsx'

function evoSpan(val, inverted) {
  if (val == null) return '—'
  const sign = val > 0 ? '+' : ''
  const cls = inverted
    ? (val < 0 ? 'text-ok' : val > 0 ? 'text-bad' : 'text-neutral')
    : (val > 0 ? 'text-ok' : val < 0 ? 'text-bad' : 'text-neutral')
  return <span className={`${cls} fw-600`}>{sign}{val.toFixed(2)}%</span>
}

export default function EvolucaoTab({ d }) {
  const { evol, evolLoading, evolHist } = d
  return (
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
          <button className="btn-small" onClick={() => { d.loadEvolution(); d.loadEvolutionHistory() }} disabled={evolLoading}>
            {evolLoading ? 'Medindo...' : '🔄 Atualizar agora'}
          </button>
        </div>

        {!evol && !evolLoading && (
          <p className="muted small pad-y-14">
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
              <div className="table-scroll mt-14">
                <h4 className="h4-tight">⚡ Mudanças detectadas</h4>
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
                          <td className={`${good == null ? 'text-neutral' : good ? 'text-ok' : 'text-bad'} fw-700`}>
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
              <p className="muted small mt-12">
                ✅ Nenhuma mudança desde o último snapshot — sistema estável.
              </p>
            )}

            {evol.current?.leagues && Object.keys(evol.current.leagues).length > 0 && (
              <div className="table-scroll mt-14">
                <h4 className="h4-tight">🎯 Métricas atuais por liga (walk-forward)</h4>
                <table className="runs">
                  <thead>
                    <tr><th>Liga</th><th>Acurácia</th><th>Brier</th><th>LogLoss</th><th>Evolução</th></tr>
                  </thead>
                  <tbody>
                    {Object.entries(evol.current.leagues)
                      .filter(([_lid, m]) => !m.error)
                      .sort((a, b) => (b[1].poisson_accuracy || 0) - (a[1].poisson_accuracy || 0))
                      .map(([lid, m]) => {
                        const evo = evol.evolution?.[lid]
                        return (
                          <tr key={lid}>
                            <td><b>{m.league_name || lid}</b></td>
                            <td>{m.poisson_accuracy}%</td>
                            <td>{m.poisson_brier}</td>
                            <td>{m.poisson_logloss ?? '—'}</td>
                            <td className="text-xs">
                              acc {evoSpan(evo?.poisson_accuracy?.pct, false)}<br/>
                              brier {evoSpan(evo?.poisson_brier?.pct, true)}
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
            <section className="card mt-16">
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
              <p className="muted small mt-8">
                Cada medição (UI ou CLI) fica gravada em <code>backend/app/data/evolution_history.jsonl</code> — nada é sobrescrito.
              </p>
            </section>
          )
        })()}

        {evolHist && evolHist.count <= 1 && (
          <p className="muted small mt-12">
            Histórico tem {evolHist.count} medição(ões). Meça novamente em momentos diferentes (após calibrações, syncs ou mudanças de modelo) para gerar a curva de tendência.
          </p>
        )}
      </section>
    </main>
  )
}
