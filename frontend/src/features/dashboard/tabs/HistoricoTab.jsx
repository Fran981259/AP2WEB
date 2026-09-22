import Stat from '../../../components/Stat.jsx'

export default function HistoricoTab({ d }) {
  return (
    <main className="column">
      <section className="panel">
        <h3>📊 Desempenho</h3>
        {d.hist && (
          <div className="hist-stats">
            <Stat label="Total" value={d.hist.stats.total} />
            <Stat label="Acertos" value={d.hist.stats.correct} ok />
            <Stat label="Erros" value={d.hist.stats.wrong} bad />
            <Stat label="Pendentes" value={d.hist.stats.pending} />
            <Stat label="Aproveitamento" value={`${d.hist.stats.hit_rate}%`} ok />
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>Minhas previsões</h3>
          <button className="btn-small" onClick={d.loadHistory} disabled={d.histLoading}>
            {d.histLoading ? 'Carregando...' : 'Atualizar'}
          </button>
        </div>
        {d.hist && d.hist.items.length === 0 && <p className="muted">Nenhuma previsão salva ainda.</p>}
        <div className="table-scroll">
          <table className="runs hist">
            <thead>
              <tr><th>Status</th><th>Jogo</th><th>Jogada</th><th>Prob.</th><th>Odd</th><th>Data</th><th></th></tr>
            </thead>
            <tbody>
              {(d.hist?.items || []).map(h => (
                <tr key={h.id}>
                  <td><span className={`badge ${h.status}`}>{h.status}</span></td>
                  <td><b>{h.home_name}</b> x <b>{h.away_name}</b></td>
                  <td>{h.pick_label}</td>
                  <td>{h.prob}%</td>
                  <td>Justa @{h.odd}</td>
                  <td>{h.created_at}</td>
                  <td><button className="btn-small" onClick={() => d.onDeletePrediction(h.id)}>✕</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  )
}
