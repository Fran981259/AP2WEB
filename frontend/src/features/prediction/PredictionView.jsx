import { useEffect, useMemo, useState } from 'react'
import Card from '../../components/Card.jsx'
import Heatmap from '../../components/Heatmap.jsx'
import { METHOD_META } from '../../utils/methodMeta.js'
import { ctxChips } from '../../utils/badges.jsx'
import DataChest from './DataChest.jsx'
import RiskPanel from './RiskPanel.jsx'

export default function PredictionView({ p, token, onSave }) {
  const { match, lambdas, probs, top_scores, proposals, compare, model } = p
  const [picked, setPicked] = useState(null)

  const pickOptions = useMemo(() => {
    const opts = []
    const p1 = probs['1x2']
    const fav = Object.keys(p1).reduce((a, b) => p1[a] >= p1[b] ? a : b)
    const favName = fav === '1' ? match.home : fav === '2' ? match.away : 'Empate'
    opts.push({ type: '1X2', value: fav, label: `1X2: ${favName}`, prob: p1[fav] })
    for (const line of [1.5, 2.5]) {
      const ov = probs['over'][`over_${line}`]
      const un = probs['under'][`under_${line}`]
      if (ov >= un) opts.push({ type: 'GOLS', value: `over_${line}`, label: `Over ${line}`, prob: ov })
      else opts.push({ type: 'GOLS', value: `under_${line}`, label: `Under ${line}`, prob: un })
    }
    const btts = probs['btts']
    if (btts['sim'] >= 0.5) opts.push({ type: 'BTTS', value: 'sim', label: 'BTTS Sim', prob: btts['sim'] })
    else opts.push({ type: 'BTTS', value: 'nao', label: 'BTTS Não', prob: btts['nao'] })
    return opts
  }, [probs, match])

  useEffect(() => { setPicked(null) }, [p])

  function save() {
    if (!picked) { alert('Escolha uma jogada para salvar'); return }
    if (!Number.isInteger(match.id) || match.id <= 0) {
      alert('Só é possível salvar previsões de uma partida agendada da base de dados.')
      return
    }
    const odd = picked.prob > 0 ? (1 / picked.prob).toFixed(2) : '—'
    onSave({
      league_id: match.league_id,
      match_id: match.id,
      home_team_id: match.home_id,
      away_team_id: match.away_id,
      home_name: match.home,
      away_name: match.away,
      match_date: match.date || null,
      pick_type: picked.type,
      pick_value: picked.value,
      pick_label: picked.label,
      prob: picked.prob,
      odd,
      payload: { lambdas, probs, top_scores },
    })
  }

  return (
    <div className="prediction">
      <div className="pred-head">
        <div>
          <h3>{match.home} <span className="vs">x</span> {match.away}</h3>
          <p className="muted small">{match.league} · {match.date}{match.kickoff ? ` · ${match.kickoff}` : ''}</p>
        </div>
        <div className="lambda-chip" title="Gols esperados do modelo Poisson">
          <b>{lambdas.home}</b> · <b>{lambdas.away}</b>
        </div>
      </div>

      <p className="experimental-notice">
        Experimental: probabilidades e mercados sao informativos, sem validacao
        temporal concluida ou garantia de desempenho.
      </p>

      {model && (model.accuracy != null || model.home_advantage) && (
        <div className="model-chip">
          🧠 modelo {match.league}: {model.feature || 'xg'} · HA {Number(model.home_advantage).toFixed(2)} · janela {model.window}
          {model.method && <> · {METHOD_META[model.method]?.icon} {METHOD_META[model.method]?.label || model.method}</>}
          {model.context && Object.values(model.context).some(Boolean) && <> · ctx {ctxChips(model.context)}</>}
          {model.accuracy != null && <> · acurácia {Number(model.accuracy).toFixed(1)}%</>}
          {model.brier != null && <> · Brier {Number(model.brier).toFixed(3)}</>}
        </div>
      )}

      {match.id && <RiskPanel match={match} token={token} />}

      {compare && compare.h2h?.length > 0 && (
        <div className="card h2h">
          <h4>⚔️ Confrontos diretos</h4>
          <div className="h2h-row">
            {compare.h2h.slice(0, 5).map((m, i) => (
              <div className="h2h-item" key={i}>
                <span className="h2h-date">{m.match_date}</span>
                <span>{m.home} <b>{m.score_home}–{m.score_away}</b> {m.away}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid-3">
        <Card title="1X2">
          {['1', 'X', '2'].map(k => {
            const v = probs['1x2'][k]
            return (
              <div className="bar-row" key={k}>
                <div className="bar-label">{k === '1' ? match.home : k === '2' ? match.away : 'Empate'}</div>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${v * 100}%` }} />
                </div>
                <div className="bar-val">{(v * 100).toFixed(1)}% <span className="odd">Justa @{probs['odds_1x2'][k]}</span></div>
              </div>
            )
          })}
        </Card>
        <Card title="Gols">
          {[1.5, 2.5, 3.5, 4.5].map(l => {
            const ov = probs['over'][`over_${l}`]
            const un = probs['under'][`under_${l}`]
            return (
              <div className="bar-row" key={l}>
                <div className="bar-label">Over {l}</div>
                <div className="bar-track">
                  <div className="bar-fill over" style={{ width: `${ov * 100}%` }} />
                </div>
                <div className="bar-val">{(ov * 100).toFixed(1)}% <span className="odd">Justa @{ov > 0 ? (1 / ov).toFixed(2) : '—'}</span>
                  <span className="muted small">U{un > 0 ? (1 / un).toFixed(2) : '—'}</span></div>
              </div>
            )
          })}
          <div className="bar-row">
            <div className="bar-label">BTTS Sim</div>
            <div className="bar-track">
              <div className="bar-fill btts" style={{ width: `${probs['btts']['sim'] * 100}%` }} />
            </div>
            <div className="bar-val">{(probs['btts']['sim'] * 100).toFixed(1)}%
              <span className="odd">Justa @{probs['btts']['sim'] > 0 ? (1 / probs['btts']['sim']).toFixed(2) : '—'}</span></div>
          </div>
        </Card>
        <Card title="Heatmap Poisson">
          <Heatmap probs={probs} lambdas={lambdas} />
        </Card>
      </div>

      <div className="grid-3">
        <Card title="Placar exato (top)">
          {top_scores.slice(0, 8).map(s => (
            <div className="row-odds" key={s.score}>
              <span>{s.score}</span>
              <span className="pct">{s.prob}%</span>
              <span className="odd">Justa @{s.odd}</span>
            </div>
          ))}
        </Card>
        <Card title="Propostas">
          <ul className="proposals">
            {proposals.map((pr, i) => (
              <li key={i}>
                <span className={`badge tipo ${pr.tipo.toLowerCase()}`}>{pr.tipo}</span> {pr.jogada}
                {pr.confianca > 0 && <span className="pct">{pr.confianca}%</span>}
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Salvar no histórico">
          <p className="muted small">Escolha a jogada e registre para acompanhar acertos/erros.</p>
          <select className="pick-select" value={picked ? JSON.stringify({ t: picked.type, v: picked.value }) : ''}
                  onChange={e => {
                    const sel = pickOptions.find(o => JSON.stringify({ t: o.type, v: o.value }) === e.target.value)
                    setPicked(sel)
                  }}>
            <option value="">— escolha —</option>
            {pickOptions.map((o, i) => (
              <option key={i} value={JSON.stringify({ t: o.type, v: o.value })}>
                {o.label} ({(o.prob * 100).toFixed(1)}%)
              </option>
            ))}
          </select>
          <button className="btn-primary btn-block" onClick={save} disabled={!picked}>
            💾 Salvar previsão
          </button>
        </Card>

        <DataChest p={p} match={match} />
      </div>
    </div>
  )
}
