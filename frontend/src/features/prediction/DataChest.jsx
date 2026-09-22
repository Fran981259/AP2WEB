import { useState } from 'react'

export default function DataChest({ p, match }) {
  const [chestOpen, setChestOpen] = useState(false)

  return (
    <div className="data-chest">
      <button className="chest-toggle" onClick={() => setChestOpen(!chestOpen)}>
        <span>🗄️ Baú de dados deste confronto</span>
        <span className={chestOpen ? 'chest-arrow open' : 'chest-arrow'}>{chestOpen ? '▲' : '▼'}</span>
      </button>
      {chestOpen && p.data && (
        <div className="chest-body">
          <div className="chest-grid">
            <div>
              <h4>📌 Dados usados nas médias (λ)</h4>
              <p className="muted small">Fonte: {p.data.source || 'sofascore'} · janela {p.data.model.window} · HA {Number(p.data.model.home_advantage).toFixed(2)}</p>
              {['home', 'away'].map(side => {
                const d = p.data[side]
                return (
                  <div key={side} className="chest-team">
                    <b>{d.name}</b>
                    <span className="muted small">média GF {d.avg.gf_avg} · GA {d.avg.ga_avg} · {d.count} jogos usados</span>
                    <table className="mini">
                      <tbody>
                        <tr><th>Data</th><th>Lado</th><th>Adversário</th><th>GF</th><th>GA</th></tr>
                        {d.games_used.map((g, i) => (
                          <tr key={i}>
                            <td>{g.date}</td><td>{g.side}</td><td>{g.opponent}</td>
                            <td>{g.gf}</td><td>{g.ga}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )
              })}
            </div>
            <div>
              <h4>⚔️ Confrontos diretos ({p.data.h2h.length})</h4>
              {p.data.h2h.length === 0 && <p className="muted small">Sem confrontos diretos no banco.</p>}
              <table className="mini">
                <tbody>
                  <tr><th>Data</th><th>Casa</th><th>Fora</th><th>Placar</th></tr>
                  {p.data.h2h.map((g, i) => (
                    <tr key={i}><td>{g.match_date}</td><td>{g.home}</td><td>{g.away}</td><td>{g.score_home}-{g.score_away}</td></tr>
                  ))}
                </tbody>
              </table>
              <h4 className="mt-14">📈 Forma recente</h4>
              {['home', 'away'].map(side => {
                const d = p.data.form[side]
                return (
                  <div key={side}>
                    <b className="small">{side === 'home' ? match.home : match.away}</b>
                    <div className="form-dots">
                      {d.map((g, i) => (
                        <span key={i} className={`fdot ${g.result === 'W' ? 'w' : g.result === 'D' ? 'd' : 'l'}`}
                              title={`${g.date} vs ${g.opponent} (${g.gf}-${g.ga})`}>
                          {g.result}
                        </span>
                      ))}
                    </div>
                  </div>
                )
              })}
              <h4 className="mt-14">🧠 Modelo calibrado</h4>
              <p className="muted small">
                {p.data.model.feature || 'xg'} · HA {Number(p.data.model.home_advantage).toFixed(2)} · janela {p.data.model.window}
                {p.data.model.accuracy != null && <> · acurácia {Number(p.data.model.accuracy).toFixed(1)}%</>}
                {p.data.model.brier != null && <> · Brier {Number(p.data.model.brier).toFixed(3)}</>}
              </p>
            </div>
          </div>
          <details className="chest-raw">
            <summary>🔍 JSON completo (tudo sem exceção)</summary>
            <pre>{JSON.stringify(p.data, null, 2)}</pre>
          </details>
        </div>
      )}
      {chestOpen && !p.data && <div className="chest-body muted small">Dados não disponíveis para este confronto.</div>}
    </div>
  )
}
