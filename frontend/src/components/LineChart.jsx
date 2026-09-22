export default function LineChart({ data, title, xLabel, yLabel }) {
  const W = 560, H = 220, P = 34
  const xs = data.map(d => d.x)
  const ys = data.map(d => d.y)
  const minX = Math.min(...xs), maxX = Math.max(...xs)
  const minY = Math.min(...ys, 0), maxY = Math.max(...ys)
  const yPad = Math.max((maxY - minY) * 0.15, 2)
  const loY = Math.max(0, minY - yPad), hiY = maxY + yPad
  const spanX = (maxX - minX) || 1, spanY = (hiY - loY) || 1
  const px = x => P + (x - minX) / spanX * (W - P * 2)
  const py = y => H - P - (y - loY) / spanY * (H - P * 2)
  const line = data.map((d, i) => `${i === 0 ? 'M' : 'L'}${px(d.x).toFixed(1)},${py(d.y).toFixed(1)}`).join(' ')
  const area = `${line} L${px(maxX).toFixed(1)},${py(loY).toFixed(1)} L${px(minX).toFixed(1)},${py(loY).toFixed(1)} Z`
  const last = data[data.length - 1]

  const step = (hiY - loY) > 60 ? 25 : 10
  const yTicks = []
  for (let t = Math.ceil(loY / step) * step; t <= hiY; t += step) yTicks.push(t)

  return (
    <div className="chart-card">
      <div className="chart-title">{title}</div>
      <svg viewBox={`0 0 ${W} ${H}`} className="line-chart">
        {yTicks.map(t => (
          <g key={t}>
            <line x1={P} x2={W - P} y1={py(t)} y2={py(t)} className="chart-grid" strokeDasharray="3 4" />
            <text x={P - 6} y={py(t) + 3} textAnchor="end" className="chart-axis-label" fontSize="10">{t}</text>
          </g>
        ))}
        <path d={area} className="chart-area" />
        <path d={line} className="chart-line" strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={px(last.x)} cy={py(last.y)} r="4" className="chart-dot" />
        <text x={px(last.x) - 6} y={py(last.y) - 8} textAnchor="end" className="chart-value" fontSize="11" fontWeight="bold">
          {last.y.toFixed(1)}%
        </text>
        <text x={P} y={H - 4} className="chart-axis-label" fontSize="10">{xLabel} · de {minX} a {maxX}</text>
        <text x={W - P} y={12} textAnchor="end" className="chart-axis-label" fontSize="10">{yLabel}</text>
      </svg>
    </div>
  )
}
