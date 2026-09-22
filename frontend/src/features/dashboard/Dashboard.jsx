import AprendizadoTab from './tabs/AprendizadoTab.jsx'
import BacktestTab from './tabs/BacktestTab.jsx'
import ConfrontoTab from './tabs/ConfrontoTab.jsx'
import DadosTab from './tabs/DadosTab.jsx'
import EvolucaoTab from './tabs/EvolucaoTab.jsx'
import HistoricoTab from './tabs/HistoricoTab.jsx'
import SofascoreTab from './tabs/SofascoreTab.jsx'
import { useDashboard } from './useDashboard.js'

const TABS = [
  ['confronto', 'Confronto'],
  ['historico', 'Histórico'],
  ['aprendizado', 'Aprendizado'],
  ['dados', 'Dados'],
  ['sofascore', 'Sofascore'],
]

export default function Dashboard({ username, role, token, onLogout }) {
  const d = useDashboard(token)
  const canOperate = role === 'operator' || role === 'admin'
  const roleLabel = role === 'admin' ? 'Administrador' : role === 'operator' ? 'Operador' : 'Leitor'
  const operationHint = canOperate ? '' : 'Esta ação exige papel de operador ou administrador.'
  const tabProps = { d, token, canOperate, operationHint }

  return (
    <div className="app">
      <header>
        <div className="brand">⚽ AP2WEB</div>
        <nav>
          {TABS.map(([id, label]) => (
            <button key={id} className={d.tab === id ? 'active' : ''} onClick={() => d.setTab(id)}>
              {label}
            </button>
          ))}
          <button className={d.tab === 'evolucao' ? 'active' : ''}
                  onClick={() => { d.setTab('evolucao'); d.loadEvolution(); d.loadEvolutionHistory() }}>
            📈 Evolução
          </button>
          <button className={d.tab === 'backtest' ? 'active' : ''}
                  onClick={() => { d.setTab('backtest'); d.loadBtStatus() }}>
            🔬 Backtest Engine
          </button>
        </nav>
        <div className="user">
          <span>{username}</span>
          <span className={`role-badge role-${role}`}>{roleLabel}</span>
          <button type="button" className="btn-link" onClick={onLogout} aria-label="Sair da conta">Sair</button>
        </div>
      </header>
      {d.error && <div className="error banner" onClick={() => d.setError('')}>✕ {d.error}</div>}

      {d.tab === 'confronto' && <ConfrontoTab {...tabProps} />}
      {d.tab === 'historico' && <HistoricoTab d={d} />}
      {d.tab === 'aprendizado' && <AprendizadoTab {...tabProps} />}
      {d.tab === 'dados' && <DadosTab d={d} />}
      {d.tab === 'sofascore' && <SofascoreTab {...tabProps} />}
      {d.tab === 'evolucao' && <EvolucaoTab d={d} />}
      {d.tab === 'backtest' && <BacktestTab {...tabProps} />}
    </div>
  )
}
