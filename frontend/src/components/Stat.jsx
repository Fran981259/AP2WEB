export default function Stat({ label, value, ok, bad, title }) {
  return (
    <div className={`stat ${ok ? 'ok' : ''} ${bad ? 'bad' : ''}`} title={title}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}
