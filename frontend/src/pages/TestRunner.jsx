import { useEffect, useRef, useState } from 'react'
import {
  FiActivity,
  FiArchive,
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
  // Left blank on purpose: a hardcoded path here only works on the one
  // machine it was typed on. The backend's browse-folder endpoint already
  // falls back to its own correct RESULTS_FOLDER whenever this is empty,
  // so leaving it blank makes the default the right one on every machine.
  const [saveRoot, setSaveRoot] = useState('')
  const [titanIp, setTitanIp] = useState('192.168.100.1')

  const [collectQxdm, setCollectQxdm] = useState(true)
  const [qxdmMode, setQxdmMode] = useState('manual')
  const [collectThroughput, setCollectThroughput] = useState(true)
  const [collectSyslog, setCollectSyslog] = useState(true)

  const [job, setJob] = useState(null)
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isFinalizingQxdm, setIsFinalizingQxdm] = useState(false)
  const [isGeneratingReport, setIsGeneratingReport] = useState(false)
  const [reportResult, setReportResult] = useState(null)

  // Which wrapper session to report-and-zip. Independent of the active
  // job above on purpose - the button used to only work for whatever
  // session was currently loaded in `job` state, so it went dead the
  // moment you navigated away, restarted the app, or wanted to generate
  // a report for an older session instead of the one just run.
  const [reportSessionFolder, setReportSessionFolder] = useState('')
  const [reportSessions, setReportSessions] = useState([])

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

        if (updatedJob?.job_id) {
          window.localStorage.setItem(
            'wncActiveWrapperJob',
            JSON.stringify({
              job_id: updatedJob.job_id,
              session_folder: updatedJob.session_folder ?? null,
              status: updatedJob.status ?? null,
              session_name: sessionName,
            })
          )
        }

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
      const response = await api.get(
        '/wrapper/browse-folder',
        {
          params: {
            current_path: saveRoot,
          },
          // Keep this request alive while the Windows folder picker is open.
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

        // Hidden compatibility defaults. Speedtest GUI now controls how
        // many tests are actually performed.
        number_of_runs: 1,
        delay_between_runs: 0,
        timeout_seconds: 180,

        qxdm_log_filename: `${sessionName.trim()}_QXDM.isf`,
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
      window.localStorage.setItem(
        'wncActiveWrapperJob',
        JSON.stringify({
          job_id: response.data.job_id,
          session_folder: response.data.session_folder ?? null,
          status: response.data.status ?? 'queued',
          session_name: sessionName.trim(),
        })
      )
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
        `/wrapper/status/${job.job_id}`,
        {
          timeout: 30000,
        }
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

  const activeSessionFolder =
    job?.session_folder ?? job?.result?.session_folder ?? null

  // Prefills the report session picker with whatever the active job just
  // produced, but only if the engineer hasn't already picked a different
  // session to report on - a finished run shouldn't silently overwrite a
  // deliberate choice to generate a report for an older session instead.
  useEffect(() => {
    if (activeSessionFolder && !reportSessionFolder) {
      setReportSessionFolder(activeSessionFolder)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionFolder])

  const loadLatestReportSession = async () => {
    try {
      const response = await api.get('/wrapper/latest-session')
      const latestFolder = response.data?.session_folder

      if (latestFolder) {
        setReportSessionFolder(latestFolder)
      }
    } catch {
      // Non-fatal - the engineer can still Browse or pick from the
      // dropdown manually.
    }
  }

  const loadReportSessions = async () => {
    try {
      const response = await api.get('/wrapper/sessions')
      setReportSessions(response.data?.sessions ?? [])
    } catch {
      // Non-fatal - the dropdown just stays empty/whatever it last had.
    }
  }

  useEffect(() => {
    loadReportSessions()
  }, [])

  const handleSelectReportSession = (event) => {
    const selectedFolder = event.target.value

    if (!selectedFolder) {
      return
    }

    setReportSessionFolder(selectedFolder)
  }

  const handleBrowseReportSession = async () => {
    setError('')

    try {
      const response = await api.get(
        '/wrapper/browse-folder',
        {
          params: {
            current_path: reportSessionFolder,
          },
          // Keep this request alive while the Windows folder picker is
          // open.
          timeout: 0,
        }
      )

      if (response.data?.path) {
        setReportSessionFolder(response.data.path)
      }
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to open the folder picker.'
      )
    }
  }

  const generateReportAndZip = async () => {
    if (!reportSessionFolder.trim() || isGeneratingReport) {
      return
    }

    setError('')
    setIsGeneratingReport(true)

    try {
      const response = await api.post(
        '/wrapper/report-and-zip',
        {
          session_folder: reportSessionFolder.trim(),
        }
      )

      setReportResult(response.data)
    } catch (requestError) {
      setReportResult(null)
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to generate the report and zip.'
      )
    } finally {
      setIsGeneratingReport(false)
    }
  }

  const openReportZipFolder = async () => {
    if (!reportResult?.zip_path) {
      return
    }

    try {
      await api.get('/wrapper/open-zip-folder', {
        params: {
          zip_path: reportResult.zip_path,
        },
      })
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to open the folder.'
      )
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
              Choose QXDM, Speedtest, and Syslog for one shared
              wrapper result folder.
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
                  Choose the test destination and the GUI tools you want
                  linked to this wrapper session.
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
                  <strong>Speedtest</strong>
                  <span>GUI throughput testing and CSV results</span>
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
                    Collect the Verizon GUI system log and save it
                    into this wrapper session
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
                  One active session for the selected GUI tools.
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

            <label className="form-field qxdm-folder-field">
              <span>Session To Report &amp; Zip</span>

              <div className="qxdm-folder-input">
                <FiFolder />

                <input
                  type="text"
                  value={reportSessionFolder}
                  onChange={(event) =>
                    setReportSessionFolder(event.target.value)
                  }
                  placeholder="Select a wrapper session folder"
                />

                <button
                  type="button"
                  className="qxdm-refresh-button"
                  onClick={handleBrowseReportSession}
                >
                  Browse
                </button>

                <button
                  type="button"
                  className="qxdm-refresh-button"
                  onClick={() => {
                    loadLatestReportSession()
                    loadReportSessions()
                  }}
                  title="Re-sync to whichever wrapper session was created most recently"
                >
                  <FiRefreshCw />
                  Use Latest
                </button>
              </div>

              <div className="qxdm-folder-input">
                <select
                  value={reportSessionFolder}
                  onChange={handleSelectReportSession}
                  onFocus={loadReportSessions}
                >
                  <option value="">
                    Or pick an existing session (
                    {reportSessions.length} found)...
                  </option>
                  {reportSessions.map((session) => (
                    <option
                      key={session.session_folder}
                      value={session.session_folder}
                    >
                      {session.session_name} -{' '}
                      {session.session_folder}
                    </option>
                  ))}
                </select>
              </div>

              <small className="qxdm-session-help">
                Not limited to the session above - pick any past
                session (current or previous) to build its report and
                zip.
              </small>
            </label>

            <div className="qxdm-action-row">
              <button
                type="button"
                className="qxdm-start-button"
                onClick={generateReportAndZip}
                disabled={
                  !reportSessionFolder.trim() ||
                  isGeneratingReport
                }
              >
                <FiArchive />
                {isGeneratingReport
                  ? 'Generating...'
                  : 'Generate Report & Zip'}
              </button>

              {reportResult?.zip_path && (
                <button
                  type="button"
                  className="qxdm-refresh-button"
                  onClick={openReportZipFolder}
                >
                  <FiFolder />
                  Open Folder
                </button>
              )}
            </div>

            {reportResult?.zip_path && (
              <div className="qxdm-manual-settings-banner">
                <strong>Session Zip</strong>
                <span>{reportResult.zip_path}</span>
              </div>
            )}

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