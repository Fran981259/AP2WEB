import { useEffect, useRef } from 'react'

/** Sequential polling: no overlapping requests; abort and stop on unmount. */
export function usePolling(fn, { interval = 2500, enabled = false, stopWhen, onTick, onError } = {}) {
  const callbacks = useRef({ fn, stopWhen, onTick, onError })
  useEffect(() => { callbacks.current = { fn, stopWhen, onTick, onError } })

  useEffect(() => {
    if (!enabled) return
    let active = true
    let timer
    let controller
    let failures = 0
    async function tick() {
      controller = new AbortController()
      try {
        const result = await callbacks.current.fn({ signal: controller.signal })
        if (!active) return
        failures = 0
        callbacks.current.onTick?.(result)
        if (callbacks.current.stopWhen?.(result)) return
      } catch (error) {
        if (!active || error.aborted) return
        failures += 1
        callbacks.current.onError?.(error)
      }
      if (active) timer = setTimeout(tick, Math.min(30000, interval * 1.5 ** failures))
    }
    tick()
    return () => {
      active = false
      clearTimeout(timer)
      controller?.abort()
    }
  }, [enabled, interval])
}
