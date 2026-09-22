import LineChart from '../../../components/LineChart.jsx'
import Stat from '../../../components/Stat.jsx'
import { flag } from '../../../utils/flags.js'
import BacktestSummary from './BacktestSummary.jsx'

export default function BacktestTab({ d, canOperate, operationHint }) {
  const { btStatus, btCvResult, btRunning, btInterval, btHistory, btMeta, btSummary, leagues } = d
  return (
    <main className="column">
      <section className="panel">
        <div className="panel-head">
          <div>
            <h3>🔬 Backtest Engine</h3>
            <p className="muted small">
              Execuções manuais experimentais de backtest e cross-validation temporal.
              Resultados não promovem automaticamente modelos de produção.
            </p>
          </div>
          <div className="btn-row">
            <label className="inline">
              Intervalo (horas)
              <input type="number" value={btInterval} min={1} max={48}
                     onChange={e => d.setBtInterval(Number(e.target.value))}
                     className="input-xs" />
            </label>
            {btStatus?.running ? (
              <button className="btn-small" onClick={d.stopBtLoop} disabled={!canOperate || !btStatus.running} title={operationHint}>
                ⏹ Parar loop
              </button>
            ) : (
              <button className="btn-primary" onClick={d.startBtLoop} disabled={!canOperate || btRunning} title={operationHint}>
                {btRunning ? 'Rodando...' : '▶ Iniciar loop'}
              </button>
            )}
            <button className="btn-primary" onClick={() => d.runBtCycle()} disabled={!canOperate || btRunning} title={operationHint}>
              {btRunning ? 'Rodando...' : '⚡ Rodar ciclo agora'}
            </button>
          </div>
        </div>

        {btStatus && (
          <div className="hist-stats mt-12">
            <Stat label="Status" value={btStatus.running ? '🟢 Rodando' : '⏹ Parado'} ok={btStatus.running} />
            <Stat label="Ciclos" value={btStatus.cycle_count || 0} />
            <Stat label="Último ciclo" value={btStatus.last_cycle_at ? new Date(btStatus.last_cycle_at).toLocaleString() : 'nunca'} />
            <Stat label="Intervalo" value={`${btStatus.interval_hours || 6}h`} />
            <Stat label="Meta records" value={btStatus.meta_history_count || 0} />
          </div>
        )}

        {btStatus?.current_phase && btStatus.running && (
          <div className="batch-progress mt-12">
            <p className="muted small">
              🔄 {btStatus.current_phase}
              {btStatus.current_league ? ` · ${btStatus.current_league}` : ''}
            </p>
          </div>
        )}

        {btStatus?.cycle_results?.length > 0 && (
          <div className="table-scroll mt-14">
            <h4 className="h4-tight">📊 Resultados do último ciclo</h4>
            <table className="runs">
              <thead>
                <tr>
                  <th>Liga</th><th>Feature</th><th>HA</th><th>Jan</th><th>Rho</th>
                  <th>Accuracy</th><th>Brier</th><th>CV Brier</th><th>Promovido</th>
                </tr>
              </thead>
              <tbody>
                {btStatus.cycle_results.map((r, i) => (
                  <tr key={i}>
                    <td><b>{r.league_name}</b></td>
                    <td>{r.current_params?.feature}</td>
                    <td>{r.current_params?.home_advantage?.toFixed(2)}</td>
                    <td>{r.current_params?.window}</td>
                    <td>{r.current_params?.rho?.toFixed(3)}</td>
                    <td>{r.backtest?.accuracy?.toFixed(1)}%</td>
                    <td>{r.backtest?.brier?.toFixed(4)}</td>
                    <td>{r.cv?.mean_brier?.toFixed(4)}</td>
                    <td>{r.promoted ? '✅' : r.error ? '❌' : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <h4>📐 Cross-Validation Temporal</h4>
            <p className="muted small">
              Validação em K folds cronológicos — treina no passado, testa no futuro.
              Zero data leakage.
            </p>
          </div>
          <select value="" onChange={e => { if (e.target.value) d.runBtCV(Number(e.target.value)) }}
                  disabled={btRunning}>
            <option value="">Selecionar liga para CV...</option>
            {leagues.map(l => (
              <option key={l.id} value={l.id}>{flag(l.country)} {l.name} ({l.played} jogos)</option>
            ))}
          </select>
        </div>

        {btCvResult && btCvResult.folds && (
          <div className="mt-12">
            <div className="hist-stats">
              <Stat label="Acurácia média" value={`${btCvResult.mean_accuracy}%`} ok={btCvResult.mean_accuracy > 50} />
              <Stat label="Brier médio" value={btCvResult.mean_brier?.toFixed(4)} />
              <Stat label="Desvio acc" value={`±${btCvResult.std_accuracy}%`} />
              <Stat label="Desvio Brier" value={`±${btCvResult.std_brier}`} />
              <Stat label="Folds" value={btCvResult.n_folds} />
            </div>
            <div className="table-scroll mt-10">
              <table className="runs">
                <thead>
                  <tr><th>Fold</th><th>Treino</th><th>Teste</th><th>Accuracy</th><th>Brier</th></tr>
                </thead>
                <tbody>
                  {btCvResult.folds.map(f => (
                    <tr key={f.fold}>
                      <td>Fold {f.fold}</td>
                      <td>{f.train_size} jogos</td>
                      <td>{f.test_size} jogos</td>
                      <td>{f.accuracy}%</td>
                      <td>{f.brier?.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {btCvResult && btCvResult.folds && btCvResult.folds.length > 1 && (
          <div className="mt-12">
            <LineChart
              data={btCvResult.folds.map(f => ({ x: f.fold, y: f.accuracy }))}
              title="Acurácia por fold temporal"
              xLabel="Fold" yLabel="Acurácia %"
            />
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <h4>🧠 Busca heurística experimental</h4>
            <p className="muted small">
              Histórico local de hiperparâmetros testados; não é otimização Bayesiana
              nem evidência para promoção de modelo.
            </p>
          </div>
          <button className="btn-small" onClick={d.loadBtStatus}>🔄 Atualizar</button>
        </div>

        {btMeta && btMeta.recent?.length > 0 && (
          <div className="table-scroll mt-12">
            <p className="muted small">📊 {btMeta.total_records} registros no histórico do meta-learner</p>
            <table className="runs mt-8">
              <thead>
                <tr>
                  <th>Liga</th><th>Feature</th><th>Window</th><th>HA</th><th>Rho</th>
                  <th>Accuracy</th><th>Brier</th><th>Data</th>
                </tr>
              </thead>
              <tbody>
                {[...btMeta.recent].reverse().slice(0, 20).map((h, i) => (
                  <tr key={i}>
                    <td>{h.league_id}</td>
                    <td>{h.feature}</td>
                    <td>{h.window}</td>
                    <td>{h.home_advantage?.toFixed(2)}</td>
                    <td>{h.rho?.toFixed(3)}</td>
                    <td>{h.accuracy?.toFixed(1)}%</td>
                    <td>{h.brier?.toFixed(4)}</td>
                    <td className="muted small">{h.timestamp?.slice(0, 16)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {btMeta && btMeta.recent?.length === 0 && (
          <p className="muted small pad-y-14">
            Nenhum registro ainda. Execute um ciclo de backtest para alimentar o meta-learner.
          </p>
        )}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h4>📋 Histórico de ciclos</h4>
          <button className="btn-small" onClick={d.loadBtStatus}>🔄 Atualizar</button>
        </div>
        {btHistory?.history?.length > 0 ? (
          <div className="table-scroll mt-12">
            <table className="runs">
              <thead>
                <tr><th>Data</th><th>Ligas</th><th>Sugestões</th><th>Status</th></tr>
              </thead>
              <tbody>
                {[...btHistory.history].reverse().map((c, i) => (
                  <tr key={i}>
                    <td>{new Date(c.timestamp).toLocaleString()}</td>
                    <td>{c.leagues_processed}</td>
                    <td>{c.meta_suggestions}</td>
                    <td><span className="badge ok">concluído</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted small pad-y-14">
            Nenhum ciclo executado ainda. Clique em "Rodar ciclo agora" para iniciar.
          </p>
        )}
      </section>

      {btSummary && btSummary.leagues?.length > 0 && <BacktestSummary summary={btSummary} />}
    </main>
  )
}
