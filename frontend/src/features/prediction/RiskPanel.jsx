import { useState } from 'react'
import { api } from '../../api.js'
import Stat from '../../components/Stat.jsx'

export default function RiskPanel({ match, token }) {
  const [risk, setRisk] = useState(null)
  const [riskLoading, setRiskLoading] = useState(false)
  const [riskKelly, setRiskKelly] = useState(0.25)
  const [riskBankroll, setRiskBankroll] = useState(1000)

  async function loadRisk() {
    if (!match.id) { alert('Previsão de confronto arbitrário — sem match_id para risco'); return }
    setRiskLoading(true)
    try {
      setRisk(await api.riskMatch(match.id, token, { kelly_fraction: riskKelly, bankroll: riskBankroll }))
    } catch (_e) { /* risco é opcional */ }
    setRiskLoading(false)
  }

  return (
    <div className="risk-panel">
      <div className="risk-header">
        <h4>🛡️ Gestão de Risco <span className="experimental-tag">experimental</span></h4>
        <div className="risk-controls">
          <label>
            Kelly
            <select value={riskKelly} onChange={e => setRiskKelly(Number(e.target.value))}>
              <option value={0.125}>1/8 Kelly</option>
              <option value={0.25}>1/4 Kelly</option>
              <option value={0.5}>1/2 Kelly</option>
              <option value={0.75}>3/4 Kelly</option>
              <option value={1}>Full Kelly</option>
            </select>
          </label>
          <label>
            Banca
            <input type="number" value={riskBankroll} min={100} step={100}
                   onChange={e => setRiskBankroll(Number(e.target.value))}
                   className="input-sm" />
          </label>
          <button className="btn-small" onClick={loadRisk} disabled={riskLoading}>
            {riskLoading ? 'Calculando...' : '📊 Calcular risco'}
          </button>
        </div>
      </div>

      {risk && (
        <div className="risk-body">
          <div className="hist-stats">
            <Stat label="Sinais" value={risk.summary.total_signals} ok={risk.summary.any_value} />
            <Stat label="Stake sugerida" value={`${risk.summary.total_stake_suggested} u`} />
            <Stat label="Exposição" value={`${risk.summary.total_exposure_pct}%`} />
            <Stat label="Mercado externo" value={risk.market.market_available ? 'Disponível' : 'Indisponível'} />
          </div>
          {risk.market.market_quote && (
            <p className="muted small mt-8">
              Quote externa: {risk.market.market_quote.provider} · capturada em {risk.market.market_quote.captured_at}
            </p>
          )}

          {risk.signals.length > 0 && (
            <div className="table-scroll mt-10">
              <table className="runs">
                <thead>
                  <tr>
                    <th>Jogada</th>
                    <th>Prob.</th>
                    <th>Odd justa do modelo</th>
                    <th>Odd externa</th>
                    <th>EV esperado</th>
                    <th>Kelly</th>
                    <th>Stake</th>
                    <th>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {risk.signals.map((s, i) => (
                    <tr key={i}>
                      <td><b>{s.label}</b></td>
                      <td>{(s.prob * 100).toFixed(1)}%</td>
                      <td>@{s.fair_odds}</td>
                      <td>@{s.market_odds}</td>
                      <td className={s.edge > 0 ? 'text-ok' : 'text-bad'}>
                        {s.edge > 0 ? '+' : ''}{(s.edge * 100).toFixed(1)}%
                      </td>
                      <td>{(s.kelly_adjusted * 100).toFixed(2)}%</td>
                      <td>{s.stake_suggested} u</td>
                      <td>
                        <span className={`badge risk-${s.risk_score.grade.toLowerCase()}`}>
                          {s.risk_score.grade} · {s.risk_score.score}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {risk.signals.length === 0 && (
            <p className="muted small mt-8">
              Odds externas não foram integradas. Fair odds são apenas referência
              do modelo e não geram edge, Kelly ou recomendação de aposta.
            </p>
          )}

          <p className="muted small mt-8">
            ⚠️ Kelly fracionado: {risk.config.kelly_label} ·
            Max stake: {risk.config.max_stake} u ·
            Max exposição/jogo: {risk.config.max_exposure_per_match} u ·
            Max diário: {risk.config.max_daily_exposure} u
          </p>
        </div>
      )}

      {!risk && !riskLoading && (
        <p className="muted small mt-6">
          Simulação informativa: não use como recomendação de aposta ou garantia de retorno.
        </p>
      )}
    </div>
  )
}
