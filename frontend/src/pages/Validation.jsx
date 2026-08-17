import { CheckCircle, AlertTriangle, XCircle, RefreshCw, ShieldCheck } from 'lucide-react'
import { useState } from 'react'

export function Validation() {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const runValidation = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/validation')
      if (!response.ok) throw new Error('Validation request failed')
      const data = await response.json()
      setReport(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'PASS':
        return <CheckCircle size={20} className="status-icon status-icon--pass" />
      case 'WARNING':
        return <AlertTriangle size={20} className="status-icon status-icon--warning" />
      case 'FAIL':
        return <XCircle size={20} className="status-icon status-icon--fail" />
      default:
        return null
    }
  }

  const getStatusClass = (status) => {
    switch (status) {
      case 'PASS':
        return 'status-badge status-badge--pass'
      case 'WARNING':
        return 'status-badge status-badge--warning'
      case 'FAIL':
        return 'status-badge status-badge--fail'
      default:
        return 'status-badge'
    }
  }

  return (
    <div className="validation">
      <div className="page-heading">
        <div>
          <span className="eyebrow">SYSTEM VALIDATION</span>
          <h1>Pipeline Health Check</h1>
          <p>Comprehensive end-to-end validation of the Annotix pipeline for the active project.</p>
        </div>
        <button
          className="primary-button primary-button--enabled"
          type="button"
          onClick={runValidation}
          disabled={loading}
        >
          {loading ? <RefreshCw size={17} className="spin" /> : <ShieldCheck size={17} />}
          {loading ? 'Running...' : 'Run Validation'}
        </button>
      </div>

      {error && (
        <div className="alert alert--error">
          <XCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      {report && (
        <>
          <section className="validation-summary">
            <div className="validation-summary__overall">
              <span className="validation-summary__label">Overall Status</span>
              <span className={getStatusClass(report.overall_status)}>
                {getStatusIcon(report.overall_status)}
                {report.overall_status}
              </span>
            </div>
            <div className="validation-summary__meta">
              <span>Project ID: <code>{report.project_id}</code></span>
              <span>Timestamp: <code>{new Date(report.timestamp).toLocaleString()}</code></span>
            </div>
          </section>

          <section className="validation-categories">
            {report.categories.map((category) => (
              <div key={category.category} className="validation-category">
                <div className="validation-category__header">
                  <h3>{category.category}</h3>
                  <span className={getStatusClass(category.status)}>
                    {getStatusIcon(category.status)}
                    {category.status}
                  </span>
                </div>

                <div className="validation-category__checks">
                  {category.checks.map((check) => (
                    <div key={check.name} className="validation-check">
                      <div className="validation-check__main">
                        <span className="validation-check__name">{check.name}</span>
                        <span className={getStatusClass(check.status)}>
                          {getStatusIcon(check.status)}
                          {check.status}
                        </span>
                      </div>
                      <div className="validation-check__message">{check.message}</div>
                      {check.details && (
                        <div className="validation-check__details">
                          <details>
                            <summary>Details</summary>
                            <pre>{check.details}</pre>
                          </details>
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {category.warnings.length > 0 && (
                  <div className="validation-category__warnings">
                    <h4>Data Quality Warnings</h4>
                    <ul>
                      {category.warnings.map((warning, idx) => (
                        <li key={idx}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </section>

          <section className="validation-summary-text">
            <h3>Summary</h3>
            <div className="validation-summary-text__grid">
              {Object.entries(report.summary).map(([category, status]) => (
                <div key={category} className="validation-summary-text__item">
                  <span className="validation-summary-text__category">{category}</span>
                  <span className={getStatusClass(status)}>{status}</span>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      {!report && !loading && !error && (
        <section className="validation-empty">
          <ShieldCheck size={48} />
          <h2>No validation report</h2>
          <p>Click "Run Validation" to perform a comprehensive health check of the Annotix pipeline.</p>
        </section>
      )}
    </div>
  )
}
