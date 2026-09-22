import { api } from '../../api.js'
import { useDashboardJobs } from './useDashboardJobs.js'
import { useDashboardState } from './useDashboardState.js'

export function useDashboard(token) {
  const s = useDashboardState()
  const jobs = useDashboardJobs(token, s)
  const {
    setLoading, setError, setSofaStatus, setCal, setBacktest, setBacktesting,
    setCurve, setCurveLoading, setEvol, setEvolLoading, setEvolHist,
    setBtRunning, setBtJob, setBtStatus, setBtCvResult,
    setCfLeague, setCfTeams, setCfHome, setCfAway, setPrediction,
    setSelLeague, setMatches, cfLeague, cfHome, cfAway, btInterval, btJob,
  } = s
  const { refreshLeagues, loadHistory, loadLearning, loadBtStatus } = jobs

  async function startSofaSync(leagueId) {
    setLoading(true); setError('')
    try {
      const res = leagueId ? await api.sofascoreSyncLeague(leagueId, token) : await api.sofascoreSync(token)
      setSofaStatus(res.job)
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  async function startCalibration() {
    setLoading(true); setError('')
    try {
      const res = await api.learningCalibrate(token)
      setCal(res.job)
      loadLearning()
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  async function runBacktest(leagueId) {
    setBacktesting(true); setBacktest(null); setError('')
    try { setBacktest(await api.learningBacktest(leagueId, token)) } catch (e) { setError(e.message) }
    setBacktesting(false)
  }

  async function loadCurve() {
    setCurveLoading(true); setError('')
    try { setCurve(await api.learningCurve(token)) } catch (e) { setError(e.message) }
    setCurveLoading(false)
  }

  async function loadEvolution() {
    setEvolLoading(true); setError('')
    try { setEvol(await api.evolutionSnapshot(token)) } catch (e) { setError(e.message) }
    setEvolLoading(false)
  }

  async function loadEvolutionHistory() {
    try { setEvolHist(await api.evolutionHistory(50, token)) } catch (_e) { /* opcional */ }
  }

  async function startBtLoop() {
    setBtRunning(true); setError('')
    try {
      const res = await api.backtestStart(btInterval, token)
      setBtJob(res.job)
      setBtStatus(previous => ({ ...previous, running: true }))
    } catch (e) { setError(e.message) }
    setBtRunning(false)
  }

  async function stopBtLoop() {
    try {
      if (btJob?.id && ['pending', 'running'].includes(btJob.status)) {
        await api.cancelJob(btJob.id, token)
        setBtJob(previous => ({ ...previous, status: 'cancelled' }))
      }
      loadBtStatus()
    } catch (e) { setError(e.message) }
  }

  async function runBtCycle(leagueIds = null) {
    setBtRunning(true); setError(''); setBtCvResult(null)
    try {
      const result = await api.backtestRun(leagueIds, token)
      setBtJob(result.job)
      setBtCvResult(result.job)
      loadBtStatus()
    } catch (e) { setError(e.message) }
    setBtRunning(false)
  }

  async function runBtCV(leagueId) {
    setBtRunning(true); setError(''); setBtCvResult(null)
    try { setBtCvResult(await api.backtestCV(leagueId, 5, token)) } catch (e) { setError(e.message) }
    setBtRunning(false)
  }

  async function onCfLeagueChange(leagueId) {
    setCfLeague(leagueId); setCfTeams([]); setCfHome(''); setCfAway(''); setPrediction(null)
    if (!leagueId) return
    setLoading(true)
    try { setCfTeams(await api.leagueTeams(leagueId, token)) } catch (e) { setError(e.message) }
    setLoading(false)
  }

  async function onCfPredict(e) {
    e.preventDefault()
    if (!cfLeague || !cfHome || !cfAway || cfHome === cfAway) {
      setError('Escolha a liga e dois times diferentes')
      return
    }
    setLoading(true); setError('')
    try {
      setPrediction(await api.predictFixture(Number(cfLeague), Number(cfHome), Number(cfAway), token))
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  async function onCfDemand() {
    if (!cfLeague) { setError('Escolha a liga primeiro'); return }
    setLoading(true); setError('')
    try {
      const res = await api.sofascoreSyncLeague(cfLeague, token)
      await refreshLeagues()
      await onCfLeagueChange(cfLeague)
      if (res.ok) {
        setSofaStatus(res.job)
        alert(`Sincronização enfileirada: job ${res.job_id}. Acompanhe na aba Sofascore.`)
      } else alert(`Falha na sincronização: ${res.error || 'erro desconhecido'}`)
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  async function selectLeague(id) {
    setSelLeague(id); setPrediction(null)
    try { setMatches(await api.leagueMatches(id, token)) } catch (e) { setError(e.message) }
  }

  async function openPrediction(id) {
    setLoading(true); setError('')
    try { setPrediction(await api.prediction(id, token)) } catch (e) { setError(e.message) }
    setLoading(false)
  }

  async function onSavePrediction(p) {
    try {
      await api.savePrediction(p, token)
      alert('Previsão salva no histórico')
      loadHistory()
    } catch (e) { setError(e.message) }
  }

  async function onDeletePrediction(id) {
    try {
      await api.deletePrediction(id, token)
      loadHistory()
    } catch (e) { setError(e.message) }
  }

  return {
    ...s,
    ...jobs,
    startSofaSync, startCalibration, runBacktest, loadCurve,
    loadEvolution, loadEvolutionHistory,
    startBtLoop, stopBtLoop, runBtCycle, runBtCV,
    onCfLeagueChange, onCfPredict, onCfDemand, selectLeague, openPrediction,
    onSavePrediction, onDeletePrediction,
  }
}
