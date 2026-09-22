import { useCallback, useEffect } from 'react'
import { api } from '../../api.js'
import { usePolling } from '../../hooks/usePolling.js'

export function useDashboardJobs(token, s) {
  const {
    tab, setLeagues, setHist, setHistLoading, setLearn, setDataQuality, setSofa,
    setSofaStatus, sofaLeague, setCal, setBtJob, setError, sofaStatus, cal, btJob,
  } = s

  const refreshLeagues = useCallback(async () => {
    const raw = await api.leagues(token)
    const byId = {}
    raw.forEach(l => { byId[l.id] = l })
    setLeagues(Object.values(byId))
  }, [token, setLeagues])

  const loadHistory = useCallback(async () => {
    setHistLoading(true)
    try { setHist(await api.predictions(token)) } catch (e) { setError(e.message) }
    setHistLoading(false)
  }, [token, setHist, setHistLoading, setError])

  const loadLearning = useCallback(async () => {
    try { setLearn(await api.learningStatus(token)) } catch (e) { setError(e.message) }
  }, [token, setLearn, setError])

  const loadDataQuality = useCallback(async () => {
    try { setDataQuality(await api.dataQuality(token)) } catch (e) { setError(e.message) }
  }, [token, setDataQuality, setError])

  const loadSofa = useCallback(async (leagueId) => {
    try { setSofa(await api.sofascoreData(leagueId, token)) } catch (e) { setError(e.message) }
  }, [token, setSofa, setError])

  const loadBtStatus = useCallback(async () => {
    try { s.setBtStatus(await api.backtestStatus(token)) } catch (e) { setError(e.message) }
    try { s.setBtHistory(await api.backtestHistory(10, token)) } catch (_e) {}
    try { s.setBtMeta(await api.backtestMeta(token)) } catch (_e) {}
    try { s.setBtSummary(await api.backtestSummary(token)) } catch (_e) {}
  }, [token, s, setError])

  useEffect(() => {
    refreshLeagues().catch(e => setError(e.message))
    if (tab === 'historico') loadHistory()
    if (tab === 'aprendizado') loadLearning()
    if (tab === 'dados') loadDataQuality()
    if (tab === 'sofascore') loadSofa()
  }, [tab, refreshLeagues, loadHistory, loadLearning, loadDataQuality, loadSofa, setError])

  usePolling(opts => api.job(sofaStatus?.id, token, opts), {
    enabled: Boolean(sofaStatus?.id && ['pending', 'running'].includes(sofaStatus.status)),
    stopWhen: j => !['pending', 'running'].includes(j.status),
    onTick: j => { setSofaStatus(j); if (!['pending', 'running'].includes(j.status)) loadSofa(sofaLeague || undefined) },
    onError: e => setError(e.message),
  })
  usePolling(opts => api.job(cal?.id, token, opts), {
    enabled: Boolean(cal?.id && ['pending', 'running'].includes(cal.status)), interval: 3000,
    stopWhen: j => !['pending', 'running'].includes(j.status),
    onTick: j => { setCal(j); if (!['pending', 'running'].includes(j.status)) loadLearning() },
    onError: e => setError(e.message),
  })
  usePolling(opts => api.job(btJob?.id, token, opts), {
    enabled: Boolean(btJob?.id && ['pending', 'running'].includes(btJob.status)), interval: 3000,
    stopWhen: j => !['pending', 'running'].includes(j.status),
    onTick: j => { setBtJob(j); if (!['pending', 'running'].includes(j.status)) loadBtStatus() },
    onError: e => setError(e.message),
  })

  return { refreshLeagues, loadHistory, loadLearning, loadDataQuality, loadSofa, loadBtStatus }
}
