import LineChart from '../../../components/LineChart.jsx'
import Stat from '../../../components/Stat.jsx'
import { ctxChips, methodBadge } from '../../../utils/badges.jsx'

export default function AprendizadoTab({ d, canOperate, operationHint }) {
  const { learn, cal, backtest, backtesting, curve, curveLoading } = d
  return (
    <main className="column">
      <section className="panel">
        <div className="panel-head">
          <div>
            <h3>🧠 Aprendizado do motor</h3>
            <p className="muted small">Fator de mando (HA) e janela deslizante calibrados por liga via backtest honesto (prevê cada jogo usando só os jogos anteriores).</p>
          </div>
          <button className="btn-primary" onClick={d.startCalibration}
                  disabled={!canOperate || d.loading || ['pending', 'running'].includes(cal?.status)} title={operationHint}>
            {['pending', 'running'].includes(cal?.status) ? `Calibrando ${Math.round((cal.progress || 0) * 100)}%...` : '⚡ Recalibrar todas'}
          </button>
        </div>

        {!learn && <div className="muted small pad-y-14">Carregando estado do aprendizado...</div>}

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
            <div className="table-scroll mt-14">
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
                        <td><button className="btn-small" onClick={() => d.runBacktest(lm.league_id)} disabled={backtesting}>Reavaliar</button></td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {backtest && (
          <div className="card mt-14">
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

        <section className="card mt-14">
          <div className="panel-head">
            <div>
              <h4>📈 Linha de aprendizado real do motor</h4>
              <p className="muted small">
                Acurácia acumulada média (1X2) por % de temporada, calculada com o backtest
                honesto em todas as ligas calibradas — cada liga com o seu modelo (feature, HA, janela).
              </p>
            </div>
            <button className="btn-small" onClick={d.loadCurve} disabled={curveLoading || ['pending', 'running'].includes(cal?.status)}>
              {curveLoading ? 'Calculando...' : (curve ? '🔄 Recalcular' : '📈 Calcular curva')}
            </button>
          </div>
          {curve && curve.series.length > 1 ? (
            <>
              <LineChart data={curve.series.map(s => ({ x: s.pct, y: s.acc }))}
                         title={`Curva média · ${curve.total_leagues} ligas · ${curve.total_played} jogos`}
                         xLabel="% da temporada" yLabel="acurácia %" />
              <p className="muted small mt-8">
                Ponto final ({curve.series[curve.series.length - 1]?.pct}%):{' '}
                <b>{curve.series[curve.series.length - 1]?.acc}%</b> de acurácia média.
              </p>
            </>
          ) : curve && (
            <p className="muted small pad-y-12">
              Sem ligas com dados suficientes ainda. Sincronize mais jogos (mín. {learn?.min_samples || 30} por liga).
            </p>
          )}
          {!curve && !curveLoading && (
            <p className="muted small pad-y-12">
              Clique em "Calcular curva" para ver como a acurácia do motor evolui conforme ele vê mais jogos.
            </p>
          )}
        </section>
      </section>
    </main>
  )
}
