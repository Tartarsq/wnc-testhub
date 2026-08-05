import { useEffect, useRef, useState } from 'react'
import {
  FiActivity,
  FiFileText,
  FiFolder,
  FiHardDrive,
  FiPlay,
  FiRefreshCw,
  FiSquare,
} from 'react-icons/fi'
import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'
import api from '../services/api'
import '../App.css'

function QXDMLogs() {
  const [logFilename, setLogFilename] = useState(
    'Titan3_QXDM_Log.isf'
  )
  const [outputFolder, setOutputFolder] = useState('')
  const [maxLogSizeMb, setMaxLogSizeMb] = useState(1024)
  const [loadMask, setLoadMask] = useState(true)
  const [continueWithoutMask, setContinueWithoutMask] =
    useState(true)
  const [sessions, setSessions] = useState([])
  const [selectedSessionId, setSelectedSessionId] = useState('')

  const [qxdmStatus, setQxdmStatus] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  const pollingRef = useRef(null)

  const stopPolling = () => {
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }

  const loadSessions = async () => {
    try {
      const response = await api.get('/sessions')
      setSessions(response.data ?? [])
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to retrieve test sessions.'
      )
    }
  }

  const loadQxdmStatus = async () => {
    try {
      const response = await api.get('/qxdm/status')
      setQxdmStatus(response.data)
      setError('')
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to retrieve QXDM status.'
      )
    } finally {
      setIsLoading(false)
    }
  }

  const startPolling = () => {
    stopPolling()

    pollingRef.current = window.setInterval(
      loadQxdmStatus,
      2000
    )
  }

  useEffect(() => {
    loadSessions()
    loadQxdmStatus()
    startPolling()

    return () => {
      stopPolling()
    }
  }, [])

  const handleStartLogging = async () => {
    if (isSubmitting || qxdmStatus?.logging_active) {
      return
    }

    setIsSubmitting(true)
    setError('')

    try {
      const payload = {
        log_filename: logFilename,
        output_folder: outputFolder.trim() || null,
        max_log_size_mb: Number(maxLogSizeMb),
        load_mask: loadMask,
        continue_without_mask: continueWithoutMask,
        session_id: selectedSessionId || null,
      }

      const response = await api.post(
        '/qxdm/start',
        payload
      )

      setQxdmStatus(response.data)
      startPolling()
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to start QXDM logging.'
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleStopLogging = async () => {
    if (isSubmitting || !qxdmStatus?.logging_active) {
      return
    }

    setIsSubmitting(true)
    setError('')

    try {
      const response = await api.post('/qxdm/stop')

      setQxdmStatus(response.data)
      startPolling()
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to stop QXDM logging.'
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const formatDateTime = (value) => {
    if (!value) {
      return 'Not available'
    }

    const parsedDate = new Date(value)

    if (Number.isNaN(parsedDate.getTime())) {
      return value
    }

    return parsedDate.toLocaleString()
  }

  const displayValue = (value) => {
    if (
      value === null ||
      value === undefined ||
      value === ''
    ) {
      return 'Not available'
    }

    return value
  }

  const loggingStatusClass =
    qxdmStatus?.status === 'logging'
      ? 'running'
      : qxdmStatus?.status === 'starting' ||
          qxdmStatus?.status === 'stopping'
        ? 'queued'
        : qxdmStatus?.status === 'failed'
          ? 'failed'
          : 'idle'

  const loggingStatusLabel = isLoading
    ? 'Checking'
    : qxdmStatus?.status ?? 'Unknown'

  const loggingActive =
    qxdmStatus?.logging_active === true

  const qxdmReady =
    qxdmStatus?.installed === true

  const progressPercent =
    qxdmStatus?.max_log_size_mb > 0
      ? Math.min(
          100,
          Math.round(
            (qxdmStatus.current_log_size_mb /
              qxdmStatus.max_log_size_mb) *
              100
          )
        )
      : 0

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="QXDM Logs" />

        <section className="page-heading">
          <div>
            <h2>QXDM Log Capture</h2>
            <p>
              Start, monitor, and stop Qualcomm diagnostic
              logging.
            </p>
          </div>

          <span
            className={`status-badge ${loggingStatusClass}`}
          >
            {loggingStatusLabel}
          </span>
        </section>

        {error && (
          <div className="api-error-message qxdm-error-message">
            <strong>QXDM error:</strong> {error}
          </div>
        )}

        <section className="qxdm-status-grid">
          <article className="qxdm-status-card">
            <div className="qxdm-status-icon">
              <FiActivity />
            </div>

            <div>
              <p>QXDM Installation</p>
              <h3>
                {qxdmReady ? 'Detected' : 'Not Found'}
              </h3>
              <span>
                {displayValue(
                  qxdmStatus?.executable_path
                )}
              </span>
            </div>
          </article>

          <article className="qxdm-status-card">
            <div className="qxdm-status-icon process">
              <FiHardDrive />
            </div>

            <div>
              <p>QXDM Process</p>
              <h3>
                {qxdmStatus?.process_running
                  ? 'Running'
                  : 'Stopped'}
              </h3>
              <span>
                Desktop automation status
              </span>
            </div>
          </article>

          <article className="qxdm-status-card">
            <div className="qxdm-status-icon logging">
              <FiFileText />
            </div>

            <div>
              <p>Logging Status</p>
              <h3>
                {loggingActive ? 'Active' : 'Inactive'}
              </h3>
              <span>
                {qxdmStatus?.message ??
                  'Waiting for QXDM status'}
              </span>
            </div>
          </article>
        </section>

        <section className="qxdm-layout-grid">
          <article className="qxdm-control-card">
            <div className="section-heading">
              <div className="section-icon">
                <FiFileText />
              </div>

              <div>
                <h3>Logging Configuration</h3>
                <p>
                  Configure the QXDM output before starting a
                  capture.
                </p>
              </div>
            </div>

            <div className="qxdm-form-grid">
              <label className="form-field qxdm-folder-field">
                <span>Test Session</span>

                <select
                  value={selectedSessionId}
                  onChange={(event) =>
                    setSelectedSessionId(event.target.value)
                  }
                  disabled={loggingActive || isSubmitting}
                >
                  <option value="">
                    No session (save to default QXDM folder)
                  </option>

                  {sessions.map((session) => (
                    <option
                      key={session.session_id}
                      value={session.session_id}
                    >
                      {session.session_name} · {session.titan_ip}
                    </option>
                  ))}
                </select>

                <small className="qxdm-session-help">
                  Selecting a session saves the log inside that
                  session&apos;s captures/qxdm folder.
                </small>
              </label>

              <label className="form-field">
                <span>Log Filename</span>

                <input
                  type="text"
                  value={logFilename}
                  onChange={(event) =>
                    setLogFilename(event.target.value)
                  }
                  disabled={
                    loggingActive || isSubmitting
                  }
                />
              </label>

              <label className="form-field">
                <span>Maximum Log Size</span>

                <div className="input-with-unit">
                  <input
                    type="number"
                    min="1"
                    max="1024"
                    value={maxLogSizeMb}
                    onChange={(event) =>
                      setMaxLogSizeMb(
                        Number(event.target.value)
                      )
                    }
                    disabled={
                      loggingActive || isSubmitting
                    }
                  />

                  <span>MB</span>
                </div>
              </label>

              <label className="form-field qxdm-folder-field">
                <span>Output Folder</span>

                <div className="qxdm-folder-input">
                  <FiFolder />

                  <input
                    type="text"
                    value={outputFolder}
                    onChange={(event) =>
                      setOutputFolder(event.target.value)
                    }
                    placeholder={
                      selectedSessionId
                        ? 'Managed automatically by the selected session'
                        : 'Leave blank to use the default results folder'
                    }
                    disabled={
                      loggingActive ||
                      isSubmitting ||
                      Boolean(selectedSessionId)
                    }
                  />
                </div>
              </label>
            </div>

            <label className="qxdm-checkbox-row">
              <input
                type="checkbox"
                checked={loadMask}
                onChange={(event) =>
                  setLoadMask(event.target.checked)
                }
                disabled={
                  loggingActive || isSubmitting
                }
              />

              <span>
                Load the configured or previously selected QXDM
                mask before logging
              </span>
            </label>

            {loadMask && (
              <label className="qxdm-checkbox-row qxdm-optional-mask-row">
                <input
                  type="checkbox"
                  checked={continueWithoutMask}
                  onChange={(event) =>
                    setContinueWithoutMask(event.target.checked)
                  }
                  disabled={
                    loggingActive || isSubmitting
                  }
                />

                <span>
                  Continue logging without a mask if no mask is
                  selected or the mask cannot be loaded
                </span>
              </label>
            )}

            <div className="qxdm-action-row">
              <button
                type="button"
                className="qxdm-start-button"
                onClick={handleStartLogging}
                disabled={
                  isSubmitting ||
                  loggingActive ||
                  !qxdmReady
                }
              >
                <FiPlay />

                {qxdmStatus?.status === 'starting'
                  ? 'Starting...'
                  : 'Start Logging'}
              </button>

              <button
                type="button"
                className="qxdm-stop-button"
                onClick={handleStopLogging}
                disabled={
                  isSubmitting || !loggingActive
                }
              >
                <FiSquare />

                {qxdmStatus?.status === 'stopping'
                  ? 'Stopping...'
                  : 'Stop Logging'}
              </button>

              <button
                type="button"
                className="qxdm-refresh-button"
                onClick={loadQxdmStatus}
                disabled={isSubmitting}
              >
                <FiRefreshCw />
                Refresh Status
              </button>
            </div>
          </article>

          <article className="qxdm-monitor-card">
            <div className="panel-header">
              <div>
                <h3>Live Capture</h3>
                <p>
                  Current QXDM log information and file size.
                </p>
              </div>

              <span
                className={`status-badge ${loggingStatusClass}`}
              >
                {loggingStatusLabel}
              </span>
            </div>

            <div className="qxdm-log-progress">
              <div className="qxdm-log-progress-header">
                <span>Log Size</span>

                <strong>
                  {qxdmStatus?.current_log_size_mb ?? 0} MB
                  {' / '}
                  {qxdmStatus?.max_log_size_mb ??
                    maxLogSizeMb}{' '}
                  MB
                </strong>
              </div>

              <div className="qxdm-log-progress-track">
                <div
                  className="qxdm-log-progress-fill"
                  style={{
                    width: `${progressPercent}%`,
                  }}
                />
              </div>

              <span className="qxdm-log-progress-percent">
                {progressPercent}% of configured maximum
              </span>
            </div>

            <dl className="qxdm-details-list">
              <div>
                <dt>Test Session</dt>
                <dd>
                  {displayValue(
                    qxdmStatus?.session_name
                  )}
                </dd>
              </div>

              <div>
                <dt>Current Log</dt>
                <dd>
                  {displayValue(
                    qxdmStatus?.current_log_path
                  )}
                </dd>
              </div>

              <div>
                <dt>Mask</dt>
                <dd>
                  {displayValue(
                    qxdmStatus?.mask_path
                  )}
                </dd>
              </div>

              <div>
                <dt>Started</dt>
                <dd>
                  {formatDateTime(
                    qxdmStatus?.started_at
                  )}
                </dd>
              </div>

              <div>
                <dt>Stopped</dt>
                <dd>
                  {formatDateTime(
                    qxdmStatus?.stopped_at
                  )}
                </dd>
              </div>
            </dl>

            {qxdmStatus?.error && (
              <div className="qxdm-status-error">
                <strong>Last error:</strong>{' '}
                {qxdmStatus.error}
              </div>
            )}
          </article>
        </section>
      </main>
    </div>
  )
}

export default QXDMLogs