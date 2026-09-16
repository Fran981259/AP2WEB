import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './styles.css'

class FrontendErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="auth-wrap">
          <div className="auth-card" role="alert">
            <div className="auth-logo">⚠️</div>
            <h1>AP2WEB</h1>
            <p className="subtitle">A interface não conseguiu iniciar.</p>
            <p className="error">{this.state.error.message || 'Erro inesperado no frontend.'}</p>
            <button className="btn-primary btn-block" onClick={() => window.location.reload()}>
              Recarregar aplicação
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <FrontendErrorBoundary><App /></FrontendErrorBoundary>
  </React.StrictMode>
)
