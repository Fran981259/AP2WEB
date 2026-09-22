export default function Heatmap({ probs, lambdas }) {
  const scores = probs['scores']
  const cells = []
  for (let i = 0; i <= 4; i++) {
    for (let j = 0; j <= 4; j++) {
      const p = scores[`${i}-${j}`] || 0
      cells.push({ i, j, p })
    }
  }
  const max = Math.max(...cells.map(c => c.p), 0.0001)
  return (
    <div>
      <div className="heat-legend">
        <span>{lambdas.home.toFixed(2)} casa →</span>
        <span className="muted">linha = gols casa · coluna = gols fora</span>
      </div>
      <div className="heatmap">
        <div className="heat-corner" />
        {[0, 1, 2, 3, 4].map(j => <div className="heat-col-label" key={j}>{j}</div>)}
        {[0, 1, 2, 3, 4].map(i => (
          <div key={i} style={{ display: 'contents' }}>
            <div className="heat-row-label">{i}</div>
            {[0, 1, 2, 3, 4].map(j => {
              const p = scores[`${i}-${j}`] || 0
              const alpha = p / max
              return (
                <div className="heat-cell" key={j}
                     style={{ background: `rgba(var(--heat-rgb),${(alpha * 0.95).toFixed(2)})` }}
                     title={`${i}-${j}: ${(p * 100).toFixed(1)}%`}>
                  {(p * 100).toFixed(0)}
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
