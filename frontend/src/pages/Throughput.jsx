import { useEffect, useRef, useState } from 'react'
import {
  FiActivity,
  FiArrowDown,
  FiArrowUp,
  FiClock,
  FiDownload,
  FiPlay,
  FiServer,
} from 'react-icons/fi'
import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'
import api from '../services/api'
import '../App.css'

function Throughput() {
  const [titanIp, setTitanIp] = useState('192.168.100.1')
  const [numberOfRuns, setNumberOfRuns] = useState(5)
  const [delaySeconds, setDelaySeconds] = useState(10)
  const [timeoutSeconds, setTimeoutSeconds] = useState(180)
  const [sessionName, setSessionName] = useState('')

  const [jobId, setJobId] = useState(null)
  const [jobStatus, setJobStatus] = useState('idle')
  const [message, setMessage] = useState(
    'Configure the test and press Start.'
  )
  const [results, setResults] = useState([])
  const [error, setError] = useState('')
  const [completedRuns, setCompletedRuns] = useState(0)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null)

  const pollingRef = useRef(null)
  const timerRef = useRef(null)

  const isRunning =
    jobStatus === 'queued' || jobStatus === 'running'

  const latestResult =
    results.length > 0 ? results[results.length - 1] : null

  const stopPolling = () => {
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }

  const stopTimer = () => {
    if (timerRef.current) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
  }

  const startTimer = () => {
    stopTimer()

    timerRef.current = window.setInterval(() => {
      setElapsedSeconds((currentValue) => currentValue + 1)
    }, 1000)
  }

  useEffect(() => {
    return () => {
      stopPolling()
      stopTimer()
    }
  }, [])

  const pollJobStatus = (currentJobId) => {
    stopPolling()

    pollingRef.current = window.setInterval(async () => {
      try {
        const response = await api.get(
          `/throughput/status/${currentJobId}`
        )

        const job = response.data

        const updatedResults = job.results ?? []

        setJobStatus(job.status)
        setMessage(job.message)
        setResults(updatedResults)
        setCompletedRuns(job.completed_runs ?? updatedResults.length)
        setLastUpdatedAt(new Date())

        window.localStorage.setItem(
          'wncThroughputStatus',
          job.status
        )

        if (updatedResults.length > 0) {
          const newestResult =
            updatedResults[updatedResults.length - 1]

          window.localStorage.setItem(
            'wncLatestThroughputResult',
            JSON.stringify(newestResult)
          )
        }

        if (job.error) {
          setError(job.error)
        }

        if (job.status === 'completed' || job.status === 'failed') {
          stopPolling()
          stopTimer()
        }
      } catch (requestError) {
        stopPolling()
        stopTimer()
        setJobStatus('failed')
        setMessage('Unable to retrieve throughput status.')

        window.localStorage.setItem(
          'wncThroughputStatus',
          'failed'
        )

        setError(
          requestError.response?.data?.detail ||
            requestError.message ||
            'Unknown request error.'
        )
      }
    }, 2000)
  }

  const getRequestErrorMessage = (requestError) => {
    const detail = requestError.response?.data?.detail

    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          const field = Array.isArray(item.loc)
            ? item.loc[item.loc.length - 1]
            : 'request'

          return `${field}: ${item.msg}`
        })
        .join(' | ')
    }

    if (typeof detail === 'string') {
      return detail
    }

    return (
      requestError.message ||
      'Unknown request error.'
    )
  }

  const handleStartTest = async () => {
    if (isRunning) {
      return
    }

    const normalizedTitanIp = titanIp.trim()
    const normalizedRuns = Number(numberOfRuns)
    const normalizedDelay = Number(delaySeconds)
    const normalizedTimeout = Number(timeoutSeconds)

    if (
      normalizedTitanIp.length < 7 ||
      normalizedTitanIp.length > 45
    ) {
      setError(
        'Titan IP must contain between 7 and 45 characters.'
      )
      return
    }

    if (
      !Number.isInteger(normalizedRuns) ||
      normalizedRuns < 1 ||
      normalizedRuns > 15
    ) {
      setError(
        'Number of runs must be a whole number from 1 to 15.'
      )
      return
    }

    if (
      !Number.isInteger(normalizedDelay) ||
      normalizedDelay < 0 ||
      normalizedDelay > 3600
    ) {
      setError(
        'Delay between runs must be a whole number from 0 to 3600 seconds.'
      )
      return
    }

    if (
      !Number.isInteger(normalizedTimeout) ||
      normalizedTimeout < 1 ||
      normalizedTimeout > 1800
    ) {
      setError(
        'Test timeout must be a whole number from 1 to 1800 seconds.'
      )
      return
    }

    setError('')
    setResults([])
    setCompletedRuns(0)
    setElapsedSeconds(0)
    setJobStatus('queued')
    setMessage('Submitting throughput test...')
    startTimer()

    window.localStorage.setItem(
      'wncThroughputStatus',
      'queued'
    )

    try {
      const response = await api.post('/throughput/start', {
        titan_ip: normalizedTitanIp,
        number_of_runs: normalizedRuns,
        delay_between_runs: normalizedDelay,
        timeout_seconds: normalizedTimeout,
      })

      const job = response.data

      setJobId(job.job_id)
      setJobStatus(job.status)
      setMessage(job.message)

      window.localStorage.setItem(
        'wncThroughputStatus',
        job.status
      )

      pollJobStatus(job.job_id)
    } catch (requestError) {
      stopTimer()
      setJobStatus('failed')
      setMessage('Unable to start throughput testing.')

      window.localStorage.setItem(
        'wncThroughputStatus',
        'failed'
      )

      setError(getRequestErrorMessage(requestError))
    }
  }

  const progressPercent =
    numberOfRuns > 0
      ? Math.min(
          100,
          Math.round((completedRuns / numberOfRuns) * 100)
        )
      : 0

  const formatElapsedTime = (totalSeconds) => {
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60

    return `${String(minutes).padStart(2, '0')}:${String(
      seconds
    ).padStart(2, '0')}`
  }

  const statusBadgeClass =
    jobStatus === 'running'
      ? 'running'
      : jobStatus === 'queued'
        ? 'queued'
        : jobStatus === 'failed'
          ? 'failed'
          : 'idle'

  const completedResults = results.filter(
    (result) => !result.notes
  )

  const averageMetric = (field) => {
    const values = completedResults
      .map((result) => Number(result[field]))
      .filter((value) => Number.isFinite(value))

    if (values.length === 0) {
      return null
    }

    return (
      values.reduce((sum, value) => sum + value, 0) /
      values.length
    )
  }

  const averageDownload = averageMetric('download_mbps')
  const averageUpload = averageMetric('upload_mbps')
  const averagePing = averageMetric('ping_ms')

  const estimatedRemainingSeconds = isRunning
    ? Math.max(
        0,
        (numberOfRuns - completedRuns) *
          (timeoutSeconds + delaySeconds)
      )
    : 0

  const formatTimestamp = (value) => {
    if (!value) {
      return 'Not updated yet'
    }

    return value.toLocaleTimeString()
  }

  const escapeCsvValue = (value) => {
    const normalized =
      value === null || value === undefined ? '' : String(value)

    return `"${normalized.replace(/"/g, '""')}"`
  }

  const handleExportResults = () => {
    if (results.length === 0) {
      return
    }

    const headers = [
      'Session',
      'Run',
      'Download Mbps',
      'Upload Mbps',
      'Ping ms',
      'Jitter ms',
      'Server',
      'Location',
      'Status',
      'Notes',
    ]

    const rows = results.map((result) => [
      sessionName.trim() || 'Unnamed session',
      result.run_number,
      result.download_mbps,
      result.upload_mbps,
      result.ping_ms,
      result.ping_jitter_ms,
      result.server_name,
      result.server_location,
      result.notes ? 'Failed' : 'Completed',
      result.notes || '',
    ])

    const csvContent = [
      headers.map(escapeCsvValue).join(','),
      ...rows.map((row) =>
        row.map(escapeCsvValue).join(',')
      ),
    ].join('\n')

    const blob = new Blob([csvContent], {
      type: 'text/csv;charset=utf-8;',
    })

    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    const safeSessionName = (
      sessionName.trim() || 'throughput-results'
    )
      .replace(/[^a-z0-9_-]+/gi, '_')
      .replace(/^_+|_+$/g, '')

    link.href = url
    link.download = `${safeSessionName || 'throughput-results'}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="Throughput" />

        <section className="page-heading">
          <div>
            <h2>Ookla Throughput Testing</h2>
            <p>
              Run real automated throughput tests through the backend.
            </p>
          </div>

          <span
            className={`status-badge ${statusBadgeClass}`}
          >
            {jobStatus}
          </span>
        </section>

        <section className="throughput-configuration">
          <div className="section-heading">
            <div className="section-icon">
              <FiActivity />
            </div>

            <div>
              <h3>Test Configuration</h3>
              <p>{message}</p>
            </div>
          </div>

          <div className="configuration-grid throughput-configuration-grid">
            <label className="form-field throughput-session-field">
              <span>Session Name</span>
              <input
                type="text"
                value={sessionName}
                onChange={(event) =>
                  setSessionName(event.target.value)
                }
                placeholder="Example: Morning LTE Validation"
                disabled={isRunning}
              />
            </label>

            <label className="form-field">
              <span>Titan IP Address</span>
              <input
                type="text"
                value={titanIp}
                onChange={(event) =>
                  setTitanIp(event.target.value)
                }
                disabled={isRunning}
              />
            </label>

            <label className="form-field">
              <span>Number of Runs</span>
              <input
                type="number"
                min="1"
                max="15"
                value={numberOfRuns}
                onChange={(event) =>
                  setNumberOfRuns(Number(event.target.value))
                }
                disabled={isRunning}
              />
            </label>

            <label className="form-field">
              <span>Delay Between Runs</span>

              <div className="input-with-unit">
                <input
                  type="number"
                  min="0"
                  value={delaySeconds}
                  onChange={(event) =>
                    setDelaySeconds(Number(event.target.value))
                  }
                  disabled={isRunning}
                />
                <span>sec</span>
              </div>
            </label>

            <label className="form-field">
              <span>Test Timeout</span>

              <div className="input-with-unit">
                <input
                  type="number"
                  min="1"
                  value={timeoutSeconds}
                  onChange={(event) =>
                    setTimeoutSeconds(Number(event.target.value))
                  }
                  disabled={isRunning}
                />
                <span>sec</span>
              </div>
            </label>
          </div>

          <div className="throughput-progress-panel">
            <div className="throughput-progress-header">
              <div>
                <span>Test Progress</span>
                <strong>
                  {completedRuns} of {numberOfRuns} runs completed
                </strong>
              </div>

              <div className="throughput-progress-time">
                <FiClock />
                <span>{formatElapsedTime(elapsedSeconds)}</span>
              </div>
            </div>

            <div
              className="throughput-progress-track"
              role="progressbar"
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuenow={progressPercent}
            >
              <div
                className="throughput-progress-fill"
                style={{ width: `${progressPercent}%` }}
              />
            </div>

            <div className="throughput-progress-footer">
              <span>{progressPercent}% complete</span>
              <span>
                {isRunning
                  ? `Run ${Math.min(
                      completedRuns + 1,
                      numberOfRuns
                    )} of ${numberOfRuns} · up to ${formatElapsedTime(
                      estimatedRemainingSeconds
                    )} remaining`
                  : jobStatus === 'completed'
                    ? 'All runs completed'
                    : 'Ready to begin'}
              </span>
            </div>
          </div>

          <div className="configuration-footer">
            <div className="configuration-note throughput-note-stack">
              <div>
                <FiServer />
                <span>
                  Ookla automatically selects an available server.
                </span>
              </div>
              <small>
                Last updated: {formatTimestamp(lastUpdatedAt)}
              </small>
            </div>

            <button
              type="button"
              className="start-throughput-button"
              onClick={handleStartTest}
              disabled={isRunning}
            >
              <FiPlay />
              {isRunning ? 'Testing...' : 'Start Throughput Test'}
            </button>
          </div>

          {error && (
            <div className="api-error-message">
              <strong>Test error:</strong> {error}
            </div>
          )}

          {jobId && (
            <p className="job-id-text">
              Job ID: <code>{jobId}</code>
            </p>
          )}
        </section>

        <section className="throughput-results-grid">
          <article className="metric-card">
            <div className="metric-icon download-icon">
              <FiArrowDown />
            </div>

            <div>
              <p>Download</p>
              <h3>
                {latestResult?.download_mbps ?? 0}
                <span> Mbps</span>
              </h3>
              <small>
                Average:{' '}
                {averageDownload !== null
                  ? `${averageDownload.toFixed(2)} Mbps`
                  : 'Not available'}
              </small>
            </div>
          </article>

          <article className="metric-card">
            <div className="metric-icon upload-icon">
              <FiArrowUp />
            </div>

            <div>
              <p>Upload</p>
              <h3>
                {latestResult?.upload_mbps ?? 0}
                <span> Mbps</span>
              </h3>
              <small>
                Average:{' '}
                {averageUpload !== null
                  ? `${averageUpload.toFixed(2)} Mbps`
                  : 'Not available'}
              </small>
            </div>
          </article>

          <article className="metric-card">
            <div className="metric-icon ping-icon">
              <FiClock />
            </div>

            <div>
              <p>Ping</p>
              <h3>
                {latestResult?.ping_ms ?? 0}
                <span> ms</span>
              </h3>
              <small>
                Average:{' '}
                {averagePing !== null
                  ? `${averagePing.toFixed(2)} ms`
                  : 'Not available'}
              </small>
            </div>
          </article>

          <article className="metric-card">
            <div className="metric-icon server-icon">
              <FiServer />
            </div>

            <div>
              <p>Completed Runs</p>
              <h3>
                {completedRuns}
                <span> / {numberOfRuns}</span>
              </h3>
            </div>
          </article>
        </section>

        <section className="dashboard-panel throughput-history-panel">
          <div className="panel-header">
            <div>
              <h3>Real Test Results</h3>
              <p>Results returned by the FastAPI backend.</p>
            </div>

            <div className="throughput-history-actions">
              <span className="history-count">
                {results.length} results
              </span>

              <button
                type="button"
                className="throughput-export-button"
                onClick={handleExportResults}
                disabled={results.length === 0}
              >
                <FiDownload />
                Export CSV
              </button>
            </div>
          </div>

          <div className="table-container">
            <table className="throughput-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Download</th>
                  <th>Upload</th>
                  <th>Ping</th>
                  <th>Jitter</th>
                  <th>Server</th>
                  <th>Location</th>
                  <th>Status</th>
                </tr>
              </thead>

              <tbody>
                {results.length === 0 ? (
                  <tr>
                    <td colSpan="8" className="empty-table-message">
                      No throughput results yet.
                    </td>
                  </tr>
                ) : (
                  results.map((result) => (
                    <tr
                      key={result.run_number}
                      className={
                        result.run_number ===
                        latestResult?.run_number
                          ? 'latest-throughput-row'
                          : ''
                      }
                    >
                      <td>{result.run_number}</td>
                      <td>
                        {result.download_mbps ?? 'N/A'} Mbps
                      </td>
                      <td>
                        {result.upload_mbps ?? 'N/A'} Mbps
                      </td>
                      <td>{result.ping_ms ?? 'N/A'} ms</td>
                      <td>
                        {result.ping_jitter_ms ?? 'N/A'} ms
                      </td>
                      <td>{result.server_name ?? 'Unknown'}</td>
                      <td>
                        {result.server_location ?? 'Unknown'}
                      </td>
                      <td>
                        <span
                          className={`table-status ${
                            result.notes ? 'failed' : 'completed'
                          }`}
                        >
                          {result.notes ? 'Failed' : 'Completed'}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  )
}

export default Throughput