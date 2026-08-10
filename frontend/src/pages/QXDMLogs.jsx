import { useEffect, useRef, useState } from 'react'
import {
  FiActivity,
  FiCheckCircle,
  FiCircle,
  FiClock,
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
  const [outputFolder, setOutputFolder] = useState('C:\\Users\\niket\\Documents\\GitHub\\wnc-testhub\\results\\qxdm_logs')
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

    const requestedFolder = outputFolder.trim()

    if (!requestedFolder) {
      setError(
        'Enter the QXDM log folder before starting the capture.'
      )
      return
    }

    setIsSubmitting(true)
    setError('')

    try {
      const payload = {
        log_filename: logFilename,
        output_folder: requestedFolder,
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

  const handleSelectSavedLog = async () => {
    if (isSubmitting || loggingActive) {
      return
    }

    setIsSubmitting(true)
    setError('')

    try {
      const response = await api.post(
        '/qxdm/saved-log/select'
      )

      setQxdmStatus(response.data)
      startPolling()
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to select the saved QXDM log.'
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleOpenSavedLogFolder = async () => {
    if (isSubmitting) {
      return
    }

    setIsSubmitting(true)
    setError('')

    try {
      const response = await api.post(
        '/qxdm/saved-log/open-folder'
      )

      setQxdmStatus(response.data)
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to open the saved QXDM log folder.'
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

  const formatFileSize = (sizeMb) => {
    if (
      sizeMb === null ||
      sizeMb === undefined ||
      Number.isNaN(Number(sizeMb))
    ) {
      return 'Not available'
    }

    return `${Number(sizeMb).toFixed(2)} MB`
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

  const workflowLabels = {
    idle: 'Idle',
    queued: 'Queued',
    launching: 'Launching QXDM',
    manual_save_settings: 'Configure Save Location',
    capture_active: 'Capture Active',
    stopping: 'Stopping Capture',
    completed: 'Completed',
    failed: 'Failed',
  }

  const workflowLabel =
    workflowLabels[qxdmStatus?.workflow_step] ??
    loggingStatusLabel

  const selectedSession = sessions.find(
    (session) => session.session_id === selectedSessionId
  )

  const suggestedDestination =
    outputFolder.trim() ||
    'Enter the QXDM log folder'

  const workflowSteps = [
    {
      id: 'launching',
      label: 'Launch QXDM',
      description: 'Open QXDM and locate the desktop window.',
    },
    {
      id: 'device',
      label: 'Connect Device',
      description: 'Wait for the diagnostic USB/COM connection.',
    },
    {
      id: 'configuration',
      label: 'Load Configuration',
      description: 'Load the selected or remembered DMC configuration.',
    },
    {
      id: 'manual_save_settings',
      label: 'Configure Save Location',
      description: 'Manually confirm the TestHub save folder in QXDM Settings.',
    },
    {
      id: 'lpm',
      label: 'Enable Airplane Mode',
      description: 'Send the mode lpm command.',
    },
    {
      id: 'online',
      label: 'Return Online',
      description: 'Send the mode online command after the delay.',
    },
    {
      id: 'capture_active',
      label: 'Capture Active',
      description: 'QXDM logging is active and ready for testing.',
    },
  ]

  const workflowOrder = {
    idle: -1,
    queued: 0,
    launching: 1,
    manual_save_settings: 4,
    capture_active: 7,
    stopping: 7,
    completed: 7,
    failed: -1,
  }

  const currentWorkflowIndex =
    workflowOrder[qxdmStatus?.workflow_step] ?? -1

  const getWorkflowStepState = (stepIndex) => {
    if (qxdmStatus?.status === 'failed') {
      return 'pending'
    }

    if (stepIndex < currentWorkflowIndex) {
      return 'complete'
    }

    if (stepIndex === currentWorkflowIndex) {
      return qxdmStatus?.status === 'completed'
        ? 'complete'
        : 'active'
    }

    return 'pending'
  }


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

        {qxdmStatus?.manual_settings_required && (
          <div className="qxdm-manual-settings-banner">
            <strong>Complete the QXDM save setup</strong>
            <span>
              QXDM capture is paused. After the 5-second delay, TestHub
              applies the filename and QXDM Log Folder automatically. Verify
              the values in QXDM, close Settings, then click Continue.
            </span>
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
                  Enter the filename and Windows save folder. TestHub
                  applies those values to QXDM after a short delay.
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
                  Selecting a session links the capture metadata to
                  that session. It does not override the save folder below.
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
                <span>QXDM Log Folder</span>

                <div className="qxdm-folder-input">
                  <FiFolder />

                  <input
                    type="text"
                    value={outputFolder}
                    onChange={(event) =>
                      setOutputFolder(event.target.value)
                    }
                    placeholder={
                      'Enter the Windows folder QXDM should use'
                    }
                    disabled={
                      loggingActive ||
                      isSubmitting
                    }
                  />
                </div>
              </label>
            </div>

            <div className="qxdm-suggested-path">
              <FiFolder />
              <div>
                <strong>Suggested destination</strong>
                <span>{suggestedDestination}</span>
                <small>
                  TestHub applies this folder to QXDM Item Store File
                  Settings after a 5-second delay, then pauses for review.
                </small>
              </div>
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
                <h3>Capture Session</h3>
                <p>
                  Reliable session status and QXDM workflow progress.
                </p>
              </div>

              <span
                className={`status-badge ${loggingStatusClass}`}
              >
                {workflowLabel}
              </span>
            </div>

            <div className="qxdm-workflow-timeline">
              {workflowSteps.map((step, index) => {
                const stepState = getWorkflowStepState(index)

                return (
                  <div
                    key={step.id}
                    className={`qxdm-workflow-step ${stepState}`}
                  >
                    <div className="qxdm-workflow-marker">
                      {stepState === 'complete' ? (
                        <FiCheckCircle />
                      ) : stepState === 'active' ? (
                        <FiClock />
                      ) : (
                        <FiCircle />
                      )}
                    </div>

                    <div className="qxdm-workflow-content">
                      <strong>{step.label}</strong>
                      <span>{step.description}</span>
                    </div>
                  </div>
                )
              })}
            </div>

            <dl className="qxdm-details-list qxdm-session-details">
              <div>
                <dt>Status</dt>
                <dd>{workflowLabel}</dd>
              </div>

              <div>
                <dt>Test Session</dt>
                <dd>
                  {displayValue(
                    qxdmStatus?.session_name
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

              <div>
                <dt>Last Status</dt>
                <dd>
                  {displayValue(
                    qxdmStatus?.message
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

        <section className="qxdm-control-card">
          <div className="section-heading">
            <div className="section-icon">
              <FiHardDrive />
            </div>

            <div>
              <h3>QXDM Log File</h3>
              <p>
                The expected path is only a TestHub suggestion. Saved log
                details appear after the real QXDM file is detected or selected.
              </p>
            </div>
          </div>

          <dl className="qxdm-details-list">
            <div>
              <dt>Expected Log Path</dt>
              <dd>
                {displayValue(
                  qxdmStatus?.expected_log_path
                )}
              </dd>
            </div>

            <div>
              <dt>Saved Filename</dt>
              <dd>
                {displayValue(
                  qxdmStatus?.current_log_filename
                )}
              </dd>
            </div>

            <div>
              <dt>Saved Path</dt>
              <dd>
                {displayValue(
                  qxdmStatus?.current_log_path
                )}
              </dd>
            </div>

            <div>
              <dt>Size</dt>
              <dd>
                {qxdmStatus?.current_log_path
                  ? formatFileSize(
                      qxdmStatus?.current_log_size_mb
                    )
                  : 'Not available'}
              </dd>
            </div>

            <div>
              <dt>Last Modified</dt>
              <dd>
                {formatDateTime(
                  qxdmStatus?.current_log_modified_at
                )}
              </dd>
            </div>
          </dl>

          <div className="qxdm-action-row">
            <button
              type="button"
              className="qxdm-refresh-button"
              onClick={handleSelectSavedLog}
              disabled={
                isSubmitting ||
                loggingActive
              }
            >
              <FiFileText />
              Select Saved Log
            </button>

            <button
              type="button"
              className="qxdm-refresh-button"
              onClick={handleOpenSavedLogFolder}
              disabled={
                isSubmitting ||
                !qxdmStatus?.current_log_path
              }
            >
              <FiFolder />
              Open Folder
            </button>
          </div>
        </section>
      </main>
    </div>
  )
}

export default QXDMLogs