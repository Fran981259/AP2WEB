import Stat from '../../../components/Stat.jsx'

export default function BacktestSummary({ summary }) {
  return (
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

        <div className="hist-stats mt-12">
          <Stat label="Acurácia geral" value={`${summary.overall.accuracy}%`} ok={summary.overall.accuracy > 50} />
          <Stat label="Brier geral" value={summary.overall.brier?.toFixed(4)} />
          <Stat label="Acertos" value={summary.overall.correct} ok />
          <Stat label="Erros" value={summary.overall.wrong} bad />
          <Stat label="Ligas" value={summary.overall.leagues_count} />
        </div>

        <div className="hist-stats mt-8">
          <Stat label="🟢 Evoluíram" value={summary.overall.evolved} ok={summary.overall.evolved > 0} />
          <Stat label="🟡 Estáveis" value={summary.overall.stable} />
          <Stat label="🔴 Reverteram" value={summary.overall.involved} bad={summary.overall.involved > 0} />
        </div>

        <div className="table-scroll mt-14">
          <table className="runs">
            <thead>
              <tr>
                <th>Trend</th><th>Liga</th><th>Accuracy</th><th>Δ Acc</th><th>Brier</th>
                <th>Δ Brier</th><th>Acertos</th><th>Erros</th><th>% Erro</th><th>Promovido</th>
              </tr>
            </thead>
            <tbody>
              {summary.leagues.map((l, i) => {
                const trendIcon = l.trend === 'evolution' ? '🟢' : l.trend === 'involution' ? '🔴' : '🟡'
                const errorRate = l.total > 0 ? (l.wrong / l.total * 100).toFixed(1) : 0
                return (
                  <tr key={i}>
                    <td className="text-lg">{trendIcon}</td>
                    <td><b>{l.league_name}</b></td>
                    <td>{l.accuracy?.toFixed(1)}%</td>
                    <td className={`fw-600 ${l.delta_accuracy > 0 ? 'text-ok' : l.delta_accuracy < 0 ? 'text-bad' : 'text-neutral'}`}>
                      {l.delta_accuracy > 0 ? '+' : ''}{l.delta_accuracy?.toFixed(1)}%
                    </td>
                    <td>{l.brier?.toFixed(4)}</td>
                    <td className={`fw-600 ${l.delta_brier < 0 ? 'text-ok' : l.delta_brier > 0 ? 'text-bad' : 'text-neutral'}`}>
                      {l.delta_brier > 0 ? '+' : ''}{l.delta_brier?.toFixed(4)}
                    </td>
                    <td className="text-ok">{l.correct}</td>
                    <td className="text-bad">{l.wrong}</td>
                    <td className={errorRate > 55 ? 'text-bad' : errorRate < 45 ? 'text-ok' : 'text-neutral'}>
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

      <section className="panel">
        <div className="panel-head">
          <div>
            <h4>🎯 Propostas de Apostas — Acurácia por Tipo</h4>
            <p className="muted small">
              Análise de acerto das propostas geradas pelo modelo em cada tipo de aposta.
            </p>
          </div>
        </div>

        <div className="hist-stats mt-12">
          {Object.entries(summary.proposals_summary || {}).map(([type, data]) => (
            <Stat key={type}
                  label={type}
                  value={data.total > 0 ? `${data.accuracy}% (${data.correct}/${data.total})` : 'sem dados'}
                  ok={data.accuracy > 55}
                  bad={data.accuracy < 45 && data.total > 10} />
          ))}
        </div>

        <div className="table-scroll mt-14">
          <table className="runs">
            <thead>
              <tr>
                <th>Tipo</th><th>Total</th><th>Acertos</th><th>Erros</th><th>Acurácia</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(summary.proposals_summary || {}).map(([type, data]) => {
                const status = data.accuracy >= 55 ? '🟢 Lucrativo' : data.accuracy >= 45 ? '🟡 Neutro' : '🔴 Prejuízo'
                return (
                  <tr key={type}>
                    <td><b>{type}</b></td>
                    <td>{data.total}</td>
                    <td className="text-ok">{data.correct}</td>
                    <td className="text-bad">{data.total - data.correct}</td>
                    <td className={`fw-600 ${data.accuracy > 55 ? 'text-ok' : data.accuracy < 45 ? 'text-bad' : 'text-neutral'}`}>
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

      <section className="panel">
        <div className="panel-head">
          <div>
            <h4>❌ Análise de Erros por Resultado</h4>
            <p className="muted small">
              Distribuição dos erros: quando o modelo erra, qual resultado real aparece mais?
            </p>
          </div>
        </div>

        <div className="table-scroll mt-12">
          <table className="runs">
            <thead>
              <tr>
                <th>Liga</th><th>Total</th><th>Erros</th><th>% Erro</th>
                <th>Erros → Casa vence</th><th>Erros → Empate</th><th>Erros → Fora vence</th>
                <th>Confiança Alta (certo)</th><th>Confiança Alta (errado)</th>
              </tr>
            </thead>
            <tbody>
              {summary.leagues.filter(l => l.wrong > 0).map((l, i) => {
                const err = l.error_analysis || {}
                const bins = err.confidence_bins || {}
                return (
                  <tr key={i}>
                    <td><b>{l.league_name}</b></td>
                    <td>{l.total}</td>
                    <td className="text-bad">{l.wrong}</td>
                    <td>{(l.wrong / l.total * 100).toFixed(1)}%</td>
                    <td>{err.errors_by_result?.['1'] || 0}</td>
                    <td>{err.errors_by_result?.['X'] || 0}</td>
                    <td>{err.errors_by_result?.['2'] || 0}</td>
                    <td className="text-ok">{bins.high_correct || 0}</td>
                    <td className="text-bad">{bins.high_wrong || 0}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
