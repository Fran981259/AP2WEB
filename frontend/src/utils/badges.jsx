import { CTX_META, METHOD_META } from './methodMeta.js'

export function methodBadge(method) {
  const m = METHOD_META[method] || METHOD_META.poisson
  return <span className={`badge method-${method || 'poisson'}`}>{m.icon} {m.label}</span>
}

export function ctxChips(ctx) {
  if (!ctx) return <span className="muted">—</span>
  const on = CTX_META.filter(([k]) => ctx[k] || ctx[k.replace('ctx_', '')]).map(([, label]) => label)
  if (on.length === 0) return <span className="muted small">base</span>
  return on.join(' · ')
}
