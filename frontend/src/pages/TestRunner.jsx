import { useEffect, useRef, useState } from 'react'
import {
  FiCheckCircle,
  FiFolder,
  FiPlay,
  FiRadio,
  FiRefreshCw,
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

  const [job, setJob] = useState(null)
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const pollingRef = useRef(null)

  const stopPolling = () => {
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }

  useEffect(() => {
    return () => {
      stopPolling()
    }
  }, [])

  const saveActiveWrapper = (wrapperJob) => {
    if (!wrapperJob?.job_id) {
      return
    }

    window.localStorage.setItem(
      'wncActiveWrapperJob',
      JSON.stringify({
        job_id: wrapperJob.job_id,
        session_folder: wrapperJob.session_folder ?? null,
        status: wrapperJob.status ?? null,
        session_name: sessionName.trim(),
      })
    )
  }

  const startPolling = (jobId) => {
    stopPolling()

    pollingRef.current = window.setInterval(async () => {
      try {
        const response = await api.get(
          `/wrapper/status/${jobId}`,
          {
            timeout: 30000,
          }
        )

        const updatedJob = response.data

        setJob(updatedJob)
        saveActiveWrapper(updatedJob)

        if (
          ['ready', 'completed', 'failed'].includes(
            updatedJob.status
          )
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
    }, 1000)
  }

  const browseFolder = async () => {
    setError('')

    try {
      const response = await api.get(
        '/wrapper/browse-folder',
        {
          params: {
            current_path: saveRoot,
          },
          timeout: 0,
        }
      )

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

    if (!titanIp.trim()) {
      setError('Enter the Titan 3 IP address.')
      return
    }

    if (!saveRoot.trim()) {
      setError('Choose a result save location.')
      return
    }

    setError('')
    setJob(null)
    setIsSubmitting(true)

    try {
      /*
       * The wrapper now only creates and activates the shared test session.
       *
       * QXDM and Speedtest are controlled from their own GUI pages.
       * These values remain in the request only because the backend request
       * model still expects them. The wrapper does not automatically run
       * throughput or QXDM from this page.
       */
      const payload = {
        session_name: sessionName.trim(),
        save_root: saveRoot.trim(),
        titan_ip: titanIp.trim(),

        collect_qxdm: true,
        qxdm_mode: 'manual',
        collect_throughput: true,
        collect_syslog: true,

        number_of_runs: 1,
        delay_between_runs: 0,
        timeout_seconds: 180,

        qxdm_log_filename:
          `${sessionName.trim()}_QXDM.isf`,
        qxdm_max_log_size_mb: 1024,
        load_mask: true,
        continue_without_mask: true,
      }

      const response = await api.post(
        '/wrapper/start',
        payload,
        {
          timeout: 30000,
        }
      )

      setJob(response.data)
      saveActiveWrapper(response.data)

      startPolling(response.data.job_id)
    } catch (requestError) {
      setIsSubmitting(false)

      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to create the wrapper session.'
      )
    }
  }

  const statusLabel = job?.status ?? 'Idle'
  const sessionFolder =
    job?.session_folder ??
    job?.result?.session_folder ??
    null

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="Test Wrapper" />

        <section className="page-heading">
          <div>
            <h2>Unified Test Session</h2>
            <p>
              Create one active result folder, then use the
              Throughput, QXDM, and PCAT pages for the actual GUI testing.
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
                <FiFolder />
              </div>

              <div>
                <h3>Start Test Session</h3>
                <p>
                  This only creates and activates the shared wrapper
                  folder. It does not automatically run Speedtest or QXDM.
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
                <span>Result Folder</span>

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

            <div className="qxdm-action-row">
              <button
                type="button"
                className="qxdm-start-button"
                onClick={startTest}
                disabled={isSubmitting}
              >
                <FiPlay />

                {isSubmitting
                  ? 'Creating Session...'
                  : 'Start Test'}
              </button>
            </div>

            {sessionFolder && (
              <div className="qxdm-manual-settings-banner">
                <strong>Active wrapper session</strong>

                <span>
                  {sessionFolder}
                </span>
              </div>
            )}
          </article>

          <article className="qxdm-monitor-card">
            <div className="panel-header">
              <div>
                <h3>Session Status</h3>

                <p>
                  Once Ready, open the individual GUI testing pages.
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
                <dt>Session Folder</dt>
                <dd>
                  {sessionFolder ?? 'Not created yet'}
                </dd>
              </div>

              <div>
                <dt>Next Step</dt>
                <dd>
                  {job?.status === 'ready'
                    ? 'Open Throughput, QXDM, or PCAT and run the GUI test.'
                    : 'Create the wrapper session first.'}
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
                    {job?.status === 'ready'
                      ? 'Session is active and ready for GUI testing.'
                      : 'Choose the result folder and click Start Test.'}
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