import { useEffect, useRef, useState } from 'react'
import {
  FiActivity,
  FiArrowDown,
  FiArrowUp,
  FiCheckCircle,
  FiCircle,
  FiClock,
  FiDownload,
  FiExternalLink,
  FiFolder,
  FiPlay,
  FiSave,
  FiServer,
} from 'react-icons/fi'
import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'
import api from '../services/api'
import '../App.css'

function Throughput() {
  const [titanIp, setTitanIp] = useState('192.168.100.1')

  const [jobId, setJobId] = useState(null)
  const [jobStatus, setJobStatus] = useState('idle')
  const [message, setMessage] = useState(
    'Open Speedtest, choose the server, and run the test.'
  )
  const [results, setResults] = useState([])
  const [error, setError] = useState('')

  const [downloadMbps, setDownloadMbps] = useState('')
  const [uploadMbps, setUploadMbps] = useState('')
  const [pingMs, setPingMs] = useState('')
  const [jitterMs, setJitterMs] = useState('')
  const [packetLoss, setPacketLoss] = useState('')
  const [serverName, setServerName] = useState('')
  const [serverLocation, setServerLocation] = useState('')
  const [serverId, setServerId] = useState('')
  const [isp, setIsp] = useState('')
  const [resultUrl, setResultUrl] = useState('')
  const [notes, setNotes] = useState('')

  const [isLaunching, setIsLaunching] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isImportingCsv, setIsImportingCsv] = useState(false)
  const [importedTestDate, setImportedTestDate] = useState('')
  const [importedTestCount, setImportedTestCount] = useState(0)
  const [csvBatchSaved, setCsvBatchSaved] = useState(false)

  // Which wrapper session should receive the imported CSV report files.
  // No native folder-picker dialog here - those weren't reliably showing
  // up on every test PC, so this reuses the same latest/dropdown pattern
  // as the Syslog page instead.
  const [wrapperFolder, setWrapperFolder] = useState('')
  const [wrapperSessions, setWrapperSessions] = useState([])

  const pollingRef = useRef(null)

  const latestResult =
    results.length > 0 ? results[results.length - 1] : null

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

  const loadLatestWrapperSession = async () => {
    try {
      const response = await api.get('/wrapper/latest-session')
      const latestFolder = response.data?.session_folder

      if (latestFolder) {
        setWrapperFolder(latestFolder)
      }
    } catch {
      // Non-fatal - the engineer can still pick a session manually.
    }
  }

  const loadWrapperSessions = async () => {
    try {
      const response = await api.get('/wrapper/sessions')
      setWrapperSessions(response.data?.sessions ?? [])
    } catch {
      // Non-fatal - the dropdown just stays empty/whatever it last had.
    }
  }

  useEffect(() => {
    loadLatestWrapperSession()
    loadWrapperSessions()
  }, [])

  const handleSelectWrapperSession = (event) => {
    const selectedFolder = event.target.value

    if (!selectedFolder) {
      return
    }

    setWrapperFolder(selectedFolder)
  }

  const handleBrowseWrapper = async () => {
    setError('')

    try {
      const response = await api.get(
        '/wrapper/browse-folder',
        {
          params: {
            current_path: wrapperFolder,
          },
          // Keep this request alive while the Windows folder picker is open.
          timeout: 0,
        }
      )

      if (response.data?.path) {
        setWrapperFolder(response.data.path)
      }
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to open the folder picker.'
      )
    }
  }


  const updateFromJob = (job) => {
    setJobId(job.job_id)
    setJobStatus(job.status)
    setMessage(job.message)
    setResults(job.results ?? [])

    window.localStorage.setItem(
      'wncThroughputStatus',
      job.status
    )

    const updatedResults = job.results ?? []

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
  }

  const pollJobStatus = (currentJobId) => {
    stopPolling()

    pollingRef.current = window.setInterval(async () => {
      try {
        const response = await api.get(
          `/throughput/status/${currentJobId}`
        )

        const job = response.data
        updateFromJob(job)

        if (
          job.status === 'waiting_for_result' ||
          job.status === 'completed' ||
          job.status === 'failed'
        ) {
          stopPolling()
          setIsLaunching(false)
        }
      } catch (requestError) {
        stopPolling()
        setIsLaunching(false)
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
    }, 1500)
  }

  const handleOpenSpeedtest = async () => {
    if (isLaunching) {
      return
    }

    setError('')
    setResults([])
    setCsvBatchSaved(false)
    setImportedTestCount(0)
    setImportedTestDate('')
    setJobStatus('queued')
    setMessage('Opening Speedtest...')
    setIsLaunching(true)

    window.localStorage.setItem(
      'wncThroughputStatus',
      'queued'
    )

    try {
      const response = await api.post(
        '/throughput/gui/launch',
        {
          titan_ip: titanIp,
        }
      )

      const job = response.data
      updateFromJob(job)
      pollJobStatus(job.job_id)
    } catch (requestError) {
      setIsLaunching(false)
      setJobStatus('failed')
      setMessage('Unable to open Speedtest.')

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
  }

  const optionalNumber = (value) =>
    value === '' ? null : Number(value)

  const handleImportLatestCsv = async () => {
    if (isImportingCsv || !jobId) {
      return
    }

    setError('')
    setIsImportingCsv(true)
    setMessage('Looking for the Speedtest CSV in Downloads...')

    try {
      const response = await api.post(
        '/throughput/gui/import-csv-latest',
        {
          job_id: jobId,
          wrapper_session_folder: wrapperFolder.trim() || null,
        },
        {
          timeout: 0,
        }
      )

      const importedResults =
        response.data?.results ?? []

      // Only bail out with nothing on the page when the CSV itself was
      // never picked/parsed. If the CSV import succeeded but the wrapper
      // folder step was cancelled or invalid, `results` still has data -
      // show it, don't discard it just because the wrapper copy didn't
      // happen.
      if (importedResults.length === 0) {
        setMessage(
          response.data?.message ||
            'Speedtest CSV import cancelled.'
        )
        return
      }

      const newest =
        response.data?.latest_result ??
        importedResults[importedResults.length - 1] ??
        {}

      setResults(importedResults)
      setJobStatus('completed')

      if (newest.download_mbps != null) {
        setDownloadMbps(String(newest.download_mbps))
      }

      if (newest.upload_mbps != null) {
        setUploadMbps(String(newest.upload_mbps))
      }

      if (newest.ping_ms != null) {
        setPingMs(String(newest.ping_ms))
      }

      if (newest.server_name) {
        setServerName(newest.server_name)
      }

      if (newest.server_location) {
        setServerLocation(newest.server_location)
      }

      setImportedTestDate(
        response.data?.latest_date ?? ''
      )

      setImportedTestCount(
        response.data?.count ?? importedResults.length
      )

      setCsvBatchSaved(importedResults.length > 0)

      if (importedResults.length > 0) {
        window.localStorage.setItem(
          'wncLatestThroughputResult',
          JSON.stringify(newest)
        )
        window.localStorage.setItem(
          'wncThroughputStatus',
          'completed'
        )
      }

      setMessage(
        response.data?.wrapper_csv_path
          ? `${response.data.message} Saved to ${response.data.wrapper_csv_path}`
          : response.data?.message ||
              'Speedtest results imported.'
      )
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to import the Speedtest CSV.'
      )
      setMessage('Speedtest CSV import failed.')
    } finally {
      setIsImportingCsv(false)
    }
  }

  const handleDownloadCsv = () => {
    if (results.length === 0) {
      setError('There are no throughput results to download yet.')
      return
    }

    setError('')

    const columns = [
      ['timestamp', 'Timestamp'],
      ['run_number', 'Run'],
      ['download_mbps', 'Download Mbps'],
      ['upload_mbps', 'Upload Mbps'],
      ['ping_ms', 'Ping ms'],
      ['ping_jitter_ms', 'Jitter ms'],
      ['packet_loss_percent', 'Packet Loss %'],
      ['server_name', 'Server Name'],
      ['server_location', 'Server Location'],
      ['connection_type', 'Connection Type'],
      ['external_ip', 'External IP'],
      ['internal_ip', 'Internal IP'],
      ['speedtest_id', 'Speedtest ID'],
    ]

    const escapeCsv = (value) => {
      const normalized =
        value === null || value === undefined
          ? ''
          : String(value)

      return `"${normalized.replaceAll('"', '""')}"`
    }

    const header = columns
      .map(([, label]) => escapeCsv(label))
      .join(',')

    const rows = results.map((result) =>
      columns
        .map(([key]) => escapeCsv(result?.[key]))
        .join(',')
    )

    const csvText = [header, ...rows].join('\r\n')

    // Add UTF-8 BOM so Excel opens the CSV cleanly on Windows.
    const csvBlob = new Blob(
      ['\uFEFF', csvText],
      {
        type: 'text/csv;charset=utf-8;',
      }
    )

    const objectUrl = URL.createObjectURL(csvBlob)
    const downloadLink = document.createElement('a')

    const dateSuffix =
      importedTestDate
        ? importedTestDate.replaceAll('/', '-')
        : new Date().toISOString().slice(0, 10)

    downloadLink.href = objectUrl
    downloadLink.download =
      `throughput_results_${dateSuffix}.csv`

    document.body.appendChild(downloadLink)
    downloadLink.click()
    downloadLink.remove()
    URL.revokeObjectURL(objectUrl)

    setMessage(
      `Downloaded ${results.length} throughput result${
        results.length === 1 ? '' : 's'
      } as CSV.`
    )
  }

  const handleSaveResult = async () => {
    if (!jobId || isSaving) {
      return
    }

    if (
      downloadMbps === '' ||
      uploadMbps === '' ||
      pingMs === '' ||
      serverName.trim() === ''
    ) {
      setError(
        'Enter download, upload, ping, and the server name before saving.'
      )
      return
    }

    setError('')
    setIsSaving(true)
    setMessage('Saving the Speedtest result...')

    try {
      const response = await api.post(
        '/throughput/gui/save',
        {
          job_id: jobId,
          download_mbps: Number(downloadMbps),
          upload_mbps: Number(uploadMbps),
          ping_ms: Number(pingMs),
          ping_jitter_ms: optionalNumber(jitterMs),
          packet_loss_percent: optionalNumber(packetLoss),
          server_name: serverName.trim(),
          server_location: serverLocation.trim(),
          server_id:
            serverId.trim() === '' ? null : serverId.trim(),
          isp: isp.trim() === '' ? null : isp.trim(),
          result_url:
            resultUrl.trim() === '' ? null : resultUrl.trim(),
          notes,
        }
      )

      updateFromJob(response.data)

      setMessage(
        'Result saved. It is now available to Analytics.'
      )
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to save the Speedtest result.'
      )
    } finally {
      setIsSaving(false)
    }
  }

  const resultEntryEnabled =
    Boolean(jobId) &&
    (
      jobStatus === 'waiting_for_result' ||
      jobStatus === 'completed'
    )

  // Explains the CSV import flow as three explicit steps. This used to
  // rely on two native Windows dialogs in a row (CSV picker, then a
  // wrapper-folder picker), but those weren't reliably showing up on
  // every test PC - it now reads the CSV straight from Downloads and
  // uses whichever wrapper session is selected above instead.
  const csvImportSteps = [
    {
      id: 'export',
      label: '1. Export from Speedtest',
      description:
        'In the Speedtest app, open Result History and export it as a CSV file (saved to Downloads).',
    },
    {
      id: 'pick',
      label: '2. Select the wrapper session, then import',
      description:
        'Pick the wrapper session above, then click "Import CSV to Wrapper" - TestHub reads the newest matching CSV from Downloads automatically.',
    },
    {
      id: 'saved',
      label: '3. Saved to Analytics',
      description:
        'Every test from the newest date in the CSV is written to the session and wrapper reports automatically.',
    },
  ]

  const csvImportStepState = (stepIndex) => {
    if (csvBatchSaved) {
      return 'complete'
    }

    if (isImportingCsv) {
      return stepIndex === 0
        ? 'complete'
        : stepIndex === 1
          ? 'active'
          : 'pending'
    }

    if (resultEntryEnabled) {
      return stepIndex === 0 ? 'active' : 'pending'
    }

    return 'pending'
  }

  const statusBadgeClass =
    jobStatus === 'failed'
      ? 'failed'
      : jobStatus === 'completed'
        ? 'completed'
        : jobStatus === 'queued' ||
            jobStatus === 'launching'
          ? 'queued'
          : jobStatus === 'waiting_for_result'
            ? 'running'
            : 'idle'

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="Throughput" />

        <section className="page-heading">
          <div>
            <h2>Speedtest GUI Throughput Testing</h2>
            <p>
              Open Speedtest from TestHub, use the suggested server or
              select another server, then save the result for Analytics.
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
              <h3>Speedtest Desktop Workflow</h3>
              <p>{message}</p>
            </div>
          </div>

          <div className="configuration-grid">
            <label className="form-field">
              <span>Titan IP Address</span>
              <input
                type="text"
                value={titanIp}
                onChange={(event) =>
                  setTitanIp(event.target.value)
                }
                disabled={isLaunching}
              />
            </label>

            <div className="form-field">
              <span>Server Selection</span>
              <div className="configuration-note">
                <FiServer />
                <span>
                  Choose the best/default server inside Speedtest, or
                  override it with a server of your choice.
                </span>
              </div>
            </div>
          </div>

          <div className="configuration-footer">
            <div className="configuration-note">
              <FiExternalLink />
              <span>
                The Speedtest GUI runs on this Windows testing computer.
              </span>
            </div>

            <button
              type="button"
              className="start-throughput-button"
              onClick={handleOpenSpeedtest}
              disabled={isLaunching}
            >
              <FiPlay />
              {isLaunching
                ? 'Opening Speedtest...'
                : 'Open Speedtest'}
            </button>
          </div>

          {error && (
            <div className="api-error-message">
              <strong>Throughput error:</strong> {error}
            </div>
          )}

          {jobId && (
            <p className="job-id-text">
              Job ID: <code>{jobId}</code>
            </p>
          )}
        </section>

        <section className="throughput-configuration">
          <div className="section-heading">
            <div className="section-icon">
              <FiSave />
            </div>

            <div>
              <h3>Save GUI Result</h3>
              <p>
                After Speedtest finishes, export Result History as CSV.
                TestHub reads the newest CSV from Downloads and imports
                every test from its newest date into the wrapper session
                selected below.
              </p>
            </div>
          </div>

          <label className="form-field qxdm-folder-field">
            <span>Wrapper Session Folder</span>

            <div className="qxdm-folder-input">
              <FiFolder />

              <input
                type="text"
                value={wrapperFolder}
                onChange={(event) =>
                  setWrapperFolder(event.target.value)
                }
                placeholder="Select Wrapper_Test_... folder"
              />

              <button
                type="button"
                className="qxdm-refresh-button"
                onClick={handleBrowseWrapper}
              >
                Browse
              </button>

              <button
                type="button"
                className="qxdm-refresh-button"
                onClick={() => {
                  loadLatestWrapperSession()
                  loadWrapperSessions()
                }}
                title="Re-sync to whichever wrapper session was created most recently"
              >
                Use Latest
              </button>
            </div>

            <div className="qxdm-folder-input">
              <select
                value={wrapperFolder}
                onChange={handleSelectWrapperSession}
                onFocus={loadWrapperSessions}
              >
                <option value="">
                  Or pick an existing session ({wrapperSessions.length}{' '}
                  found)...
                </option>
                {wrapperSessions.map((session) => (
                  <option
                    key={session.session_folder}
                    value={session.session_folder}
                  >
                    {session.session_name} - {session.session_folder}
                  </option>
                ))}
              </select>
            </div>

            <small className="qxdm-session-help">
              Optional - if left blank, the CSV import is saved to
              Analytics only. Select a session to also copy the report
              into its reports subfolder.
            </small>
          </label>

          <div className="qxdm-workflow-timeline">
            {csvImportSteps.map((step, index) => {
              const stepState = csvImportStepState(index)

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

          <div className="configuration-grid">
            <div className="form-field">
              <span>Imported Test Date</span>
              <input
                type="text"
                value={importedTestDate}
                readOnly
                placeholder="No CSV result imported yet"
              />
            </div>

            <div className="form-field">
              <span>Tests Imported</span>
              <input
                type="text"
                value={
                  importedTestCount > 0
                    ? String(importedTestCount)
                    : ''
                }
                readOnly
                placeholder="0"
              />
            </div>
          </div>

          <div className="configuration-footer">
            <div className="configuration-note">
              <FiActivity />
              {isImportingCsv ? (
                <span>
                  Reading the newest Speedtest CSV from Downloads...
                </span>
              ) : !resultEntryEnabled ? (
                <span>
                  Click &quot;Open Speedtest&quot; above first — this button
                  unlocks once a Speedtest session is ready for a result.
                </span>
              ) : (
                <span>
                  Export Result History as CSV in Speedtest first - TestHub
                  picks up the newest CSV in Downloads automatically, no
                  file picker needed.
                </span>
              )}
            </div>

            <button
              type="button"
              className="start-throughput-button"
              onClick={handleImportLatestCsv}
              disabled={
                !resultEntryEnabled ||
                isImportingCsv
              }
            >
              <FiExternalLink />
              {isImportingCsv
                ? 'Reading CSV from Downloads...'
                : 'Import CSV to Wrapper'}
            </button>
          </div>

          <div className="configuration-grid">
            <label className="form-field">
              <span>Download Mbps *</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={downloadMbps}
                onChange={(event) =>
                  setDownloadMbps(event.target.value)
                }
                disabled={!resultEntryEnabled}
              />
            </label>

            <label className="form-field">
              <span>Upload Mbps *</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={uploadMbps}
                onChange={(event) =>
                  setUploadMbps(event.target.value)
                }
                disabled={!resultEntryEnabled}
              />
            </label>

            <label className="form-field">
              <span>Ping ms *</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={pingMs}
                onChange={(event) =>
                  setPingMs(event.target.value)
                }
                disabled={!resultEntryEnabled}
              />
            </label>

            <label className="form-field">
              <span>Jitter ms</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={jitterMs}
                onChange={(event) =>
                  setJitterMs(event.target.value)
                }
                disabled={!resultEntryEnabled}
              />
            </label>

            <label className="form-field">
              <span>Packet Loss %</span>
              <input
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={packetLoss}
                onChange={(event) =>
                  setPacketLoss(event.target.value)
                }
                disabled={!resultEntryEnabled}
              />
            </label>

            <label className="form-field">
              <span>Server Name *</span>
              <input
                type="text"
                value={serverName}
                onChange={(event) =>
                  setServerName(event.target.value)
                }
                disabled={!resultEntryEnabled}
                placeholder="Example: Verizon"
              />
            </label>

            <label className="form-field">
              <span>Server Location</span>
              <input
                type="text"
                value={serverLocation}
                onChange={(event) =>
                  setServerLocation(event.target.value)
                }
                disabled={!resultEntryEnabled}
                placeholder="Example: Bridgewater, NJ"
              />
            </label>

            <label className="form-field">
              <span>Server ID</span>
              <input
                type="text"
                value={serverId}
                onChange={(event) =>
                  setServerId(event.target.value)
                }
                disabled={!resultEntryEnabled}
              />
            </label>

            <label className="form-field">
              <span>ISP</span>
              <input
                type="text"
                value={isp}
                onChange={(event) =>
                  setIsp(event.target.value)
                }
                disabled={!resultEntryEnabled}
              />
            </label>

            <label className="form-field">
              <span>Result URL</span>
              <input
                type="text"
                value={resultUrl}
                onChange={(event) =>
                  setResultUrl(event.target.value)
                }
                disabled={!resultEntryEnabled}
              />
            </label>

            <label className="form-field">
              <span>Notes</span>
              <input
                type="text"
                value={notes}
                onChange={(event) =>
                  setNotes(event.target.value)
                }
                disabled={!resultEntryEnabled}
              />
            </label>
          </div>

          <div className="configuration-footer">
            <div className="configuration-note">
              <FiActivity />
              <span>
                CSV imports are saved to Analytics automatically. Use
                Save Result only when entering one result manually.
              </span>
            </div>

            <button
              type="button"
              className="start-throughput-button"
              onClick={handleSaveResult}
              disabled={
                !resultEntryEnabled ||
                isSaving ||
                csvBatchSaved
              }
            >
              <FiSave />
              {csvBatchSaved
                ? `${importedTestCount} CSV Tests Already Saved`
                : isSaving
                  ? 'Saving Result...'
                  : 'Save Manual Result'}
            </button>
          </div>
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
            </div>
          </article>

          <article className="metric-card">
            <div className="metric-icon server-icon">
              <FiServer />
            </div>
            <div>
              <p>Server</p>
              <h3>
                {latestResult?.server_name ?? 'Not saved'}
              </h3>
            </div>
          </article>
        </section>

        <section className="dashboard-panel throughput-history-panel">
          <div className="panel-header">
            <div>
              <h3>Current GUI Test Result</h3>
              <p>
                Saved results use the same fields as the existing
                throughput and Analytics workflow.
              </p>
            </div>

            <div className="throughput-history-actions">
              <span className="history-count">
                {results.length}{' '}
                {results.length === 1 ? 'result' : 'results'}
              </span>

              <button
                type="button"
                className="throughput-export-button"
                onClick={handleDownloadCsv}
                disabled={results.length === 0}
              >
                <FiDownload />
                Download CSV
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
                      Open Speedtest and save a result to see it here.
                    </td>
                  </tr>
                ) : (
                  results.map((result) => (
                    <tr key={`${result.timestamp}-${result.run_number}`}>
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
                        <span className="table-status completed">
                          Completed
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