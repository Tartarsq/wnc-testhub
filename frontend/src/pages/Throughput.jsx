import { useEffect, useRef, useState } from 'react'
import {
  FiActivity,
  FiArrowDown,
  FiArrowUp,
  FiClock,
  FiExternalLink,
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
                After Speedtest finishes, enter the values shown in the
                GUI. TestHub saves them in the existing Analytics format.
              </p>
            </div>
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
                Saving creates an Excel report that the existing Analytics
                page can read automatically.
              </span>
            </div>

            <button
              type="button"
              className="start-throughput-button"
              onClick={handleSaveResult}
              disabled={!resultEntryEnabled || isSaving}
            >
              <FiSave />
              {isSaving
                ? 'Saving Result...'
                : 'Save Result'}
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

            <span className="history-count">
              {results.length} result
            </span>
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