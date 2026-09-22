import { useMemo, useState } from 'react'
import { CONTINENT_ORDER, continent } from '../../utils/flags.js'

export function useDashboardState() {
  const [tab, setTab] = useState('confronto')
  const [showMethodNotice, setShowMethodNotice] = useState(true)
  const [leagues, setLeagues] = useState([])
  const [dataQuality, setDataQuality] = useState(null)
  const [selLeague, setSelLeague] = useState(null)
  const [matches, setMatches] = useState([])
  const [prediction, setPrediction] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [cfLeague, setCfLeague] = useState('')
  const [cfTeams, setCfTeams] = useState([])
  const [cfHome, setCfHome] = useState('')
  const [cfAway, setCfAway] = useState('')

  const [hist, setHist] = useState(null)
  const [leagueSearch, setLeagueSearch] = useState('')
  const [openConts, setOpenConts] = useState(() => new Set(['Europa']))
  const [learn, setLearn] = useState(null)
  const [cal, setCal] = useState(null)
  const [backtest, setBacktest] = useState(null)
  const [backtesting, setBacktesting] = useState(false)
  const [curve, setCurve] = useState(null)
  const [curveLoading, setCurveLoading] = useState(false)

  const [sofa, setSofa] = useState(null)
  const [sofaStatus, setSofaStatus] = useState(null)
  const [sofaLeague, setSofaLeague] = useState('')
  const [sofaSelFields, setSofaSelFields] = useState(['xg', 'possession', 'shots_on_target', 'corners', 'yellow_cards'])
  const [sofaTeamFilter, setSofaTeamFilter] = useState('')
  const [histLoading, setHistLoading] = useState(false)

  const [evol, setEvol] = useState(null)
  const [evolLoading, setEvolLoading] = useState(false)
  const [evolHist, setEvolHist] = useState(null)

  const [btStatus, setBtStatus] = useState(null)
  const [btJob, setBtJob] = useState(null)
  const [btHistory, setBtHistory] = useState(null)
  const [btMeta, setBtMeta] = useState(null)
  const [btCvResult, setBtCvResult] = useState(null)
  const [btRunning, setBtRunning] = useState(false)
  const [btInterval, setBtInterval] = useState(6)
  const [btSummary, setBtSummary] = useState(null)

  const filteredLeagues = useMemo(() => {
    const q = leagueSearch.trim().toLowerCase()
    if (!q) return leagues
    return leagues.filter(l =>
      l.name.toLowerCase().includes(q) || (l.country || '').toLowerCase().includes(q))
  }, [leagues, leagueSearch])

  const groupedByContinent = useMemo(() => {
    const groups = {}
    for (const l of filteredLeagues) {
      const key = continent(l.country)
      if (!groups[key]) groups[key] = []
      groups[key].push(l)
    }
    return Object.entries(groups).sort((a, b) => {
      const ia = CONTINENT_ORDER.indexOf(a[0])
      const ib = CONTINENT_ORDER.indexOf(b[0])
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
    })
  }, [filteredLeagues])

  const selLeagueObj = selLeague ? leagues.find(l => l.id === selLeague) : null

  function toggleCont(c) {
    setOpenConts(prev => {
      const next = new Set(prev)
      if (next.has(c)) next.delete(c)
      else next.add(c)
      return next
    })
  }

  return {
    tab, setTab, showMethodNotice, setShowMethodNotice,
    leagues, setLeagues, dataQuality, setDataQuality,
    selLeague, setSelLeague, matches, setMatches, prediction, setPrediction,
    error, setError, loading, setLoading,
    cfLeague, setCfLeague, cfTeams, setCfTeams, cfHome, setCfHome, cfAway, setCfAway,
    hist, setHist, leagueSearch, setLeagueSearch, openConts,
    learn, setLearn, cal, setCal, backtest, setBacktest, backtesting, setBacktesting,
    curve, setCurve, curveLoading, setCurveLoading,
    sofa, setSofa, sofaStatus, setSofaStatus, sofaLeague, setSofaLeague,
    sofaSelFields, setSofaSelFields, sofaTeamFilter, setSofaTeamFilter, histLoading, setHistLoading,
    evol, setEvol, evolLoading, setEvolLoading, evolHist, setEvolHist,
    btStatus, setBtStatus, btJob, setBtJob, btHistory, setBtHistory,
    btMeta, setBtMeta, btCvResult, setBtCvResult, btRunning, setBtRunning,
    btInterval, setBtInterval, btSummary, setBtSummary,
    filteredLeagues, groupedByContinent, selLeagueObj, toggleCont,
  }
}
