import { useEffect, useRef, useState } from 'react'
import {
  FiActivity,
  FiCheckCircle,
  FiDatabase,
  FiFileText,
  FiFolder,
  FiPlay,
  FiRadio,
  FiRefreshCw,
  FiSettings,
} from 'react-icons/fi'
import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'
import api from '../services/api'
import '../App.css'

function TestRunner() {
  const [sessionName, setSessionName] = useState('Titan3_Test')
  const [saveRoot, setSaveRoot] = useState(
    'C:\\Users\\niket\\Documents\\GitHub\\wnc-testhub\\results'
  )
  const [titanIp, setTitanIp] = useState('192.168.100.1')

  const [collectQxdm, setCollectQxdm] = useState(true)
  const [qxdmMode, setQxdmMode] = useState('manual')
  const [collectThroughput, setCollectThroughput] = useState(true)
  const [collectSyslog, setCollectSyslog] = useState(true)

  const [numberOfRuns, setNumberOfRuns] = useState(5)
  const [delayBetweenRuns, setDelayBetweenRuns] = useState(10)
  const [timeoutSeconds, setTimeoutSeconds] = useState(180)

  const [job, setJob] = useState(null)
  const [syslogStatus, setSyslogStatus] = useState(null)
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isFinalizingQxdm, setIsFinalizingQxdm] = useState(false)

  const pollingRef = useRef(null)

  const stopPolling = () => {
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }

  const loadSyslogStatus = async () => {
    try {
      const response = await api.get('/wrapper/syslog/status')
      setSyslogStatus(response.data)
    } catch {
      setSyslogStatus(null)
    }
  }

  useEffect(() => {
    loadSyslogStatus()

    return () => {
      stopPolling()
    }
  }, [])

  const startPolling = (jobId) => {
    stopPolling()

    pollingRef.current = window.setInterval(async () => {
      try {
        const response = await api.get(
          `/wrapper/status/${jobId}`
        )

        const updatedJob = response.data
        setJob(updatedJob)

        if (
          [
            'completed',
            'failed',
            'ready',
            'awaiting_qxdm_stop',
          ].includes(updatedJob.status)
        ) {
          stopPolling()
          setIsSubmitting(false)
        }
      } catch (requestError) {
        stopPolling()
        setIsSubmitting(false)
        setError(
          requestError.response?.data?.detail ||
            requestError.message ||
            'Unable to retrieve wrapper status.'
        )
      }
    }, 2000)
  }

  const browseFolder = async () => {
    setError('')

    try {
      const response = await api.get('/wrapper/browse-folder')

      if (response.data?.path) {
        setSaveRoot(response.data.path)
      }
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to open the folder picker.'
      )
    }
  }

  const startTest = async () => {
    if (isSubmitting) {
      return
    }

    if (!sessionName.trim()) {
      setError('Enter a test/session name.')
      return
    }

    if (!saveRoot.trim()) {
      setError('Choose a result save location.')
      return
    }

    if (!collectQxdm && !collectThroughput && !collectSyslog) {
      setError('Select at least one test artifact.')
      return
    }

    setError('')
    setIsSubmitting(true)
    setJob(null)

    try {
      const payload = {
        session_name: sessionName.trim(),
        save_root: saveRoot.trim(),
        titan_ip: titanIp.trim(),

        collect_qxdm: collectQxdm,
        qxdm_mode: collectQxdm ? qxdmMode : 'manual',

        collect_throughput: collectThroughput,
        collect_syslog: collectSyslog,

        number_of_runs: Number(numberOfRuns),
        delay_between_runs: Number(delayBetweenRuns),
        timeout_seconds: Number(timeoutSeconds),

        qxdm_log_filename: `${sessionName.trim()}_QXDM.isf`,
        qxdm_max_log_size_mb: 1024,
        load_mask: true,
        continue_without_mask: true,
      }

      const response = await api.post(
        '/wrapper/start',
        payload
      )

      setJob(response.data)
      startPolling(response.data.job_id)
    } catch (requestError) {
      setIsSubmitting(false)
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to start the wrapper test.'
      )
    }
  }

  const finalizeQxdmLog = async () => {
    if (!job?.job_id || isFinalizingQxdm) {
      return
    }

    setError('')
    setIsFinalizingQxdm(true)

    try {
      const response = await api.post(
        `/wrapper/qxdm/finalize/${job.job_id}`
      )

      const statusResponse = await api.get(
        `/wrapper/status/${job.job_id}`
      )

      setJob(statusResponse.data)
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to finalize the QXDM log.'
      )
    } finally {
      setIsFinalizingQxdm(false)
    }
  }

  const statusLabel = job?.status ?? 'Idle'

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="Test Wrapper" />

        <section className="page-heading">
          <div>
            <h2>Unified Test Session</h2>
            <p>
              Store QXDM, throughput, and syslog artifacts under one
              test result folder.
            </p>
          </div>

          <span className="status-badge idle">
            {statusLabel}
          </span>
        </section>

        {error && (
          <div className="api-error-message">
            <strong>Wrapper error:</strong> {error}
          </div>
        )}

        <section className="qxdm-layout-grid">
          <article className="qxdm-control-card">
            <div className="section-heading">
              <div className="section-icon">
                <FiSettings />
              </div>

              <div>
                <h3>Test Configuration</h3>
                <p>
                  Choose the test destination and which artifacts TestHub
                  should collect.
                </p>
              </div>
            </div>

            <div className="qxdm-form-grid">
              <label className="form-field">
                <span>Test Name</span>
                <input
                  value={sessionName}
                  onChange={(event) =>
                    setSessionName(event.target.value)
                  }
                  disabled={isSubmitting}
                />
              </label>

              <label className="form-field">
                <span>Titan 3 IP</span>
                <input
                  value={titanIp}
                  onChange={(event) =>
                    setTitanIp(event.target.value)
                  }
                  disabled={isSubmitting}
                />
              </label>

              <label className="form-field qxdm-folder-field">
                <span>Save Location</span>

                <div className="qxdm-folder-input">
                  <FiFolder />

                  <input
                    value={saveRoot}
                    onChange={(event) =>
                      setSaveRoot(event.target.value)
                    }
                    disabled={isSubmitting}
                  />

                  <button
                    type="button"
                    className="qxdm-refresh-button"
                    onClick={browseFolder}
                    disabled={isSubmitting}
                  >
                    Browse
                  </button>
                </div>
              </label>
            </div>

            <div className="wrapper-artifact-grid">
              <label className="wrapper-artifact-card">
                <input
                  type="checkbox"
                  checked={collectQxdm}
                  onChange={(event) =>
                    setCollectQxdm(event.target.checked)
                  }
                  disabled={isSubmitting}
                />

                <FiDatabase />

                <div>
                  <strong>QXDM Log</strong>
                  <span>Qualcomm diagnostic capture</span>
                </div>
              </label>

              <label className="wrapper-artifact-card">
                <input
                  type="checkbox"
                  checked={collectThroughput}
                  onChange={(event) =>
                    setCollectThroughput(event.target.checked)
                  }
                  disabled={isSubmitting}
                />

                <FiActivity />

                <div>
                  <strong>Throughput Report</strong>
                  <span>Download, upload, latency report</span>
                </div>
              </label>

              <label className="wrapper-artifact-card">
                <input
                  type="checkbox"
                  checked={collectSyslog}
                  onChange={(event) =>
                    setCollectSyslog(event.target.checked)
                  }
                  disabled={isSubmitting}
                />

                <FiFileText />

                <div>
                  <strong>Syslog</strong>
                  <span>
                    {syslogStatus?.configured
                      ? 'Collector configured'
                      : 'Collector command still required'}
                  </span>
                </div>
              </label>
            </div>

            {collectQxdm && (
              <div className="qxdm-control-card wrapper-qxdm-mode-panel">
                <div className="section-heading">
                  <div className="section-icon">
                    <FiDatabase />
                  </div>

                  <div>
                    <h3>QXDM Logging Mode</h3>
                    <p>
                      Choose whether the QXDM portion of this test should
                      use manual setup or the automatic QXDM workflow.
                    </p>
                  </div>
                </div>

                <div className="wrapper-mode-grid">
                  <button
                    type="button"
                    className={`wrapper-mode-card ${
                      qxdmMode === 'manual' ? 'selected' : ''
                    }`}
                    onClick={() => setQxdmMode('manual')}
                    disabled={isSubmitting}
                  >
                    <FiSettings />

                    <strong>Manual QXDM</strong>

                    <span>
                      TestHub only opens QXDM and gives you 60 seconds.
                      You control the mask, save location, logging, and modem
                      commands yourself.
                    </span>
                  </button>

                  <button
                    type="button"
                    className={`wrapper-mode-card ${
                      qxdmMode === 'automatic' ? 'selected' : ''
                    }`}
                    onClick={() => setQxdmMode('automatic')}
                    disabled={isSubmitting}
                  >
                    <FiActivity />

                    <strong>Automatic QXDM</strong>

                    <span>
                      TestHub runs the QXDM controller startup sequence.
                      The current controller may still pause for QXDM Item
                      Store File setup if your build cannot set it reliably.
                    </span>
                  </button>
                </div>
              </div>
            )}

            {collectThroughput && (
              <div className="qxdm-form-grid wrapper-throughput-config">
                <label className="form-field">
                  <span>Throughput Runs</span>

                  <input
                    type="number"
                    min="1"
                    max="15"
                    value={numberOfRuns}
                    onChange={(event) =>
                      setNumberOfRuns(event.target.value)
                    }
                    disabled={isSubmitting}
                  />
                </label>

                <label className="form-field">
                  <span>Delay Between Runs</span>

                  <input
                    type="number"
                    min="0"
                    value={delayBetweenRuns}
                    onChange={(event) =>
                      setDelayBetweenRuns(event.target.value)
                    }
                    disabled={isSubmitting}
                  />
                </label>

                <label className="form-field">
                  <span>Timeout</span>

                  <input
                    type="number"
                    min="1"
                    value={timeoutSeconds}
                    onChange={(event) =>
                      setTimeoutSeconds(event.target.value)
                    }
                    disabled={isSubmitting}
                  />
                </label>
              </div>
            )}

            <div className="qxdm-action-row">
              <button
                type="button"
                className="qxdm-start-button"
                onClick={startTest}
                disabled={isSubmitting}
              >
                <FiPlay />

                {isSubmitting
                  ? 'Starting...'
                  : 'Start Test'}
              </button>

              {collectQxdm && job?.job_id && (
                <button
                  type="button"
                  className="qxdm-refresh-button"
                  onClick={finalizeQxdmLog}
                  disabled={isFinalizingQxdm}
                >
                  <FiFolder />
                  {isFinalizingQxdm
                    ? 'Finalizing...'
                    : 'Finalize QXDM Log'}
                </button>
              )}
            </div>
          </article>

          <article className="qxdm-monitor-card">
            <div className="panel-header">
              <div>
                <h3>Wrapper Progress</h3>
                <p>
                  One session, one destination, all selected artifacts.
                </p>
              </div>

              <FiRefreshCw />
            </div>

            <dl className="qxdm-details-list">
              <div>
                <dt>Status</dt>
                <dd>{statusLabel}</dd>
              </div>

              <div>
                <dt>QXDM Mode</dt>
                <dd>
                  {collectQxdm
                    ? job?.result?.qxdm_mode ?? qxdmMode
                    : 'Not selected'}
                </dd>
              </div>

              <div>
                <dt>Session Folder</dt>
                <dd>
                  {job?.session_folder ??
                    job?.result?.session_folder ??
                    'Not created yet'}
                </dd>
              </div>

              <div>
                <dt>Collected QXDM Log</dt>
                <dd>
                  {job?.result?.qxdm_log_path ??
                    'Not finalized yet'}
                </dd>
              </div>
            </dl>

            <div className="wrapper-progress-list">
              {(job?.progress ?? []).map((item, index) => (
                <div
                  key={`${item.step}-${index}`}
                  className="wrapper-progress-item"
                >
                  <FiCheckCircle />

                  <div>
                    <strong>
                      {item.step} · {item.status}
                    </strong>

                    <span>{item.message}</span>
                  </div>
                </div>
              ))}

              {!job?.progress?.length && (
                <div className="wrapper-progress-empty">
                  <FiRadio />

                  <span>
                    Configure the session and start when ready.
                  </span>
                </div>
              )}
            </div>
          </article>
        </section>
      </main>
    </div>
  )
}

export default TestRunner