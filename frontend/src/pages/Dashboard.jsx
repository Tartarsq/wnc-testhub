import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FiActivity,
  FiArrowDown,
  FiArrowRight,
  FiClock,
  FiCpu,
  FiDatabase,
  FiFileText,
  FiPlay,
  FiRefreshCw,
  FiServer,
  FiWifi,
  FiZap,
} from 'react-icons/fi'
import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'
import api from '../services/api'
import '../App.css'

function Dashboard() {
  const navigate = useNavigate()

  const [device, setDevice] = useState(null)
  const [qxdmStatus, setQxdmStatus] = useState(null)
  const [sessions, setSessions] = useState([])
  const [latestThroughput, setLatestThroughput] = useState(null)
  const [throughputRunCount, setThroughputRunCount] = useState(0)
  const [throughputStatus, setThroughputStatus] = useState('idle')
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [error, setError] = useState('')

  const loadDashboardData = async (showRefreshState = false) => {
    if (showRefreshState) setIsRefreshing(true)

    try {
      const [
        deviceResponse,
        qxdmResponse,
        sessionsResponse,
        analyticsResponse,
      ] = await Promise.allSettled([
        api.get('/device/status', {
          params: { titan_ip: '192.168.100.1' },
        }),
        api.get('/qxdm/status'),
        api.get('/sessions'),
        api.get('/analytics'),
      ])

      if (deviceResponse.status === 'fulfilled') {
        setDevice(deviceResponse.value.data)
      }

      if (qxdmResponse.status === 'fulfilled') {
        setQxdmStatus(qxdmResponse.value.data)
      }

      if (sessionsResponse.status === 'fulfilled') {
        setSessions(sessionsResponse.value.data ?? [])
      }

      if (analyticsResponse.status === 'fulfilled') {
        const analytics = analyticsResponse.value.data
        const history = analytics?.history ?? []

        setThroughputRunCount(
          analytics?.summary?.total_runs ?? history.length
        )

        if (history.length > 0) {
          setLatestThroughput(history[0])
          setThroughputStatus('completed')

          window.localStorage.setItem(
            'wncLatestThroughputResult',
            JSON.stringify(history[0])
          )
          window.localStorage.setItem(
            'wncThroughputStatus',
            'completed'
          )
        }
      }

      const failures = [
        deviceResponse,
        qxdmResponse,
        sessionsResponse,
        analyticsResponse,
      ].filter((result) => result.status === 'rejected')

      if (failures.length === 4) {
        throw new Error('Unable to load dashboard data.')
      }

      setError('')
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to load dashboard data.'
      )
    } finally {
      setIsLoading(false)
      setIsRefreshing(false)
    }
  }

  useEffect(() => {
    loadDashboardData()

    const storedResult = window.localStorage.getItem(
      'wncLatestThroughputResult'
    )
    const storedStatus = window.localStorage.getItem(
      'wncThroughputStatus'
    )

    if (storedResult) {
      try {
        setLatestThroughput(JSON.parse(storedResult))
      } catch {
        window.localStorage.removeItem('wncLatestThroughputResult')
      }
    }

    if (storedStatus) setThroughputStatus(storedStatus)

    const interval = window.setInterval(loadDashboardData, 8000)
    return () => window.clearInterval(interval)
  }, [])

  const currentDownload =
    latestThroughput?.download_mbps !== null &&
    latestThroughput?.download_mbps !== undefined
      ? `${latestThroughput.download_mbps} Mbps`
      : 'Not available'

  const currentUpload =
    latestThroughput?.upload_mbps !== null &&
    latestThroughput?.upload_mbps !== undefined
      ? `${latestThroughput.upload_mbps} Mbps`
      : 'Not available'

  const currentPing =
    latestThroughput?.ping_ms !== null &&
    latestThroughput?.ping_ms !== undefined
      ? `${latestThroughput.ping_ms} ms`
      : 'Not available'

  const qxdmRunning = qxdmStatus?.process_running === true
  const qxdmLogging = qxdmStatus?.logging_active === true

  const activeSession = useMemo(() => {
    if (qxdmStatus?.session_id) {
      return sessions.find(
        (session) => session.session_id === qxdmStatus.session_id
      )
    }

    return sessions.find(
      (session) =>
        session.status === 'active' || session.status === 'running'
    )
  }, [qxdmStatus?.session_id, sessions])

  const sessionName =
    qxdmStatus?.session_name ||
    activeSession?.session_name ||
    'No active session'

  const formatDateTime = (value) => {
    if (!value) return 'Not available'
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
  }

  const throughputBadgeClass =
    throughputStatus === 'running'
      ? 'running'
      : throughputStatus === 'queued'
        ? 'queued'
        : throughputStatus === 'failed'
          ? 'failed'
          : 'idle'

  const throughputBadgeLabel =
    throughputStatus === 'running'
      ? 'Running'
      : throughputStatus === 'queued'
        ? 'Queued'
        : throughputStatus === 'completed'
          ? 'Completed'
          : throughputStatus === 'failed'
            ? 'Failed'
            : 'Idle'

  const activityItems = [
    {
      title: qxdmLogging
        ? 'QXDM capture is active'
        : qxdmRunning
          ? 'QXDM is running'
          : 'QXDM is stopped',
      detail: qxdmStatus?.message || 'Waiting for QXDM status.',
      active: qxdmRunning,
    },
    {
      title: device?.reachable
        ? 'Titan 3 connected'
        : 'Titan 3 disconnected',
      detail: device?.reachable
        ? `Reachable at ${device.ip_address}`
        : 'Check the Titan network connection.',
      active: device?.reachable,
    },
    {
      title:
        throughputStatus === 'completed'
          ? 'Throughput test completed'
          : throughputStatus === 'running'
            ? 'Throughput test running'
            : 'Throughput testing idle',
      detail: latestThroughput
        ? `Latest download: ${currentDownload} · ${throughputRunCount} saved run${throughputRunCount === 1 ? '' : 's'}`
        : 'No throughput result has been saved yet.',
      active:
        throughputStatus === 'running' ||
        throughputStatus === 'completed',
    },
    {
      title: activeSession
        ? `Session: ${activeSession.session_name}`
        : 'No active test session',
      detail: activeSession
        ? `Created ${formatDateTime(activeSession.created_at)}`
        : 'Create or select a session before testing.',
      active: Boolean(activeSession),
    },
  ]

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="Dashboard" />

        <section className="dashboard-header mission-control-header">
          <div>
            <p className="dashboard-eyebrow">WNC TestHub Mission Control</p>
            <h2>Test Bench Overview</h2>
            <p>
              Monitor device health, QXDM automation, sessions, and
              throughput results from one place.
            </p>
          </div>

          <div className="dashboard-header-actions">
            <button
              className="dashboard-refresh-button"
              type="button"
              onClick={() => loadDashboardData(true)}
              disabled={isRefreshing}
            >
              <FiRefreshCw className={isRefreshing ? 'spinning' : ''} />
              Refresh
            </button>

            <button
              className="start-test-button"
              type="button"
              onClick={() => navigate('/throughput')}
            >
              <FiPlay />
              Start New Test
            </button>
          </div>
        </section>

        {error && (
          <div className="api-error-message dashboard-api-error">
            <strong>Dashboard notice:</strong> {error}
          </div>
        )}

        <section className="mission-status-grid">
          <article className="mission-status-card">
            <span className="mission-status-icon backend"><FiServer /></span>
            <div><p>Backend</p><h3>{error ? 'Limited' : 'Online'}</h3><span>FastAPI service status</span></div>
            <span className={`mission-health-dot ${error ? 'warning' : 'online'}`} />
          </article>

          <article className="mission-status-card">
            <span className="mission-status-icon device"><FiWifi /></span>
            <div><p>Device</p><h3>{isLoading ? 'Checking' : device?.reachable ? 'Connected' : 'Disconnected'}</h3><span>{device?.ip_address ?? '192.168.100.1'}</span></div>
            <span className={`mission-health-dot ${device?.reachable ? 'online' : 'offline'}`} />
          </article>

          <article className="mission-status-card">
            <span className="mission-status-icon qxdm"><FiDatabase /></span>
            <div><p>QXDM</p><h3>{qxdmRunning ? 'Running' : 'Stopped'}</h3><span>{qxdmLogging ? 'Capture active' : 'Desktop automation status'}</span></div>
            <span className={`mission-health-dot ${qxdmRunning ? 'online' : 'offline'}`} />
          </article>

          <article className="mission-status-card">
            <span className="mission-status-icon session"><FiActivity /></span>
            <div><p>Session</p><h3>{activeSession || qxdmStatus?.session_name ? 'Active' : 'Idle'}</h3><span>{sessionName}</span></div>
            <span className={`mission-health-dot ${activeSession || qxdmStatus?.session_name ? 'online' : 'idle'}`} />
          </article>
        </section>

        <section className="mission-primary-grid">
          <article className="dashboard-panel mission-session-panel">
            <div className="panel-header">
              <div><h3>Current Session</h3><p>Active QXDM capture and session information.</p></div>
              <span className={`status-badge ${qxdmLogging ? 'running' : 'idle'}`}>{qxdmLogging ? 'Logging' : 'Idle'}</span>
            </div>

            <div className="mission-session-hero">
              <span className="mission-session-icon"><FiFileText /></span>
              <div><p>Session Name</p><h4>{sessionName}</h4><span>{qxdmStatus?.message ?? 'No QXDM workflow is currently active.'}</span></div>
            </div>

            <dl className="mission-details-grid">
              <div><dt>Workflow</dt><dd>{qxdmStatus?.workflow_step ?? qxdmStatus?.status ?? 'Idle'}</dd></div>
              <div><dt>Started</dt><dd>{formatDateTime(qxdmStatus?.started_at)}</dd></div>
              <div><dt>Mask</dt><dd>{qxdmStatus?.mask_path ?? 'Not available'}</dd></div>
              <div><dt>Process</dt><dd>{qxdmRunning ? 'Running' : 'Stopped'}</dd></div>
            </dl>

            <button type="button" className="dashboard-panel-link" onClick={() => navigate('/qxdm-logs')}>
              Open QXDM Logs <FiArrowRight />
            </button>
          </article>

          <article className="dashboard-panel mission-device-panel">
            <div className="panel-header">
              <div><h3>Device Information</h3><p>Current Titan 3 radio and network status.</p></div>
              <span className={`status-badge ${device?.reachable ? 'running' : 'failed'}`}>{device?.reachable ? 'Connected' : 'Disconnected'}</span>
            </div>

            <div className="dashboard-device-summary">
              <div className="dashboard-device-icon"><FiCpu /></div>
              <div><h4>Titan 3</h4><p>{device?.ip_address ?? '192.168.100.1'}</p></div>
            </div>

            <dl className="mission-device-details">
              <div><dt>Firmware</dt><dd>{device?.firmware_version ?? 'Not available'}</dd></div>
              <div><dt>Carrier</dt><dd>{device?.carrier ?? 'Not available'}</dd></div>
              <div><dt>Technology</dt><dd>{device?.technology ?? 'Not available'}</dd></div>
              <div><dt>Band</dt><dd>{device?.serving_band ?? 'Not available'}</dd></div>
              <div><dt>Signal</dt><dd>{device?.rsrp_dbm !== null && device?.rsrp_dbm !== undefined ? `${device.rsrp_dbm} dBm` : 'Not available'}</dd></div>
            </dl>

            <button type="button" className="dashboard-panel-link" onClick={() => navigate('/devices')}>
              View Device Details <FiArrowRight />
            </button>
          </article>
        </section>

        <section className="mission-secondary-grid">
          <article className="dashboard-panel throughput-panel">
            <div className="panel-header">
              <div><h3>Throughput Summary</h3><p>Latest result · {throughputRunCount} saved run{throughputRunCount === 1 ? '' : 's'}.</p></div>
              <span className={`status-badge ${throughputBadgeClass}`}>{throughputBadgeLabel}</span>
            </div>

            <div className="dashboard-throughput-results">
              <div className="dashboard-throughput-item"><span className="dashboard-throughput-icon download"><FiArrowDown /></span><div><p>Download</p><strong>{currentDownload}</strong></div></div>
              <div className="dashboard-throughput-item"><span className="dashboard-throughput-icon upload"><FiActivity /></span><div><p>Upload</p><strong>{currentUpload}</strong></div></div>
              <div className="dashboard-throughput-item"><span className="dashboard-throughput-icon ping"><FiWifi /></span><div><p>Ping</p><strong>{currentPing}</strong></div></div>
            </div>

            <button type="button" className="dashboard-panel-link" onClick={() => navigate('/throughput')}>
              View Throughput Testing <FiArrowRight />
            </button>
          </article>

          <article className="dashboard-panel mission-activity-panel">
            <div className="panel-header"><div><h3>Recent Activity</h3><p>Latest system and testing events.</p></div><FiClock /></div>
            <div className="mission-activity-list">
              {activityItems.map((item) => (
                <div key={item.title} className="mission-activity-item">
                  <span className={`mission-activity-marker ${item.active ? 'active' : ''}`} />
                  <div><strong>{item.title}</strong><span>{item.detail}</span></div>
                </div>
              ))}
            </div>
          </article>

          <article className="dashboard-panel mission-actions-panel">
            <div className="panel-header"><div><h3>Quick Actions</h3><p>Open the most common testing workflows.</p></div><FiZap /></div>
            <div className="mission-action-grid">
              <button type="button" onClick={() => navigate('/qxdm-logs')}><FiFileText /><span><strong>QXDM Logs</strong><small>Start or stop capture</small></span></button>
              <button type="button" onClick={() => navigate('/throughput')}><FiActivity /><span><strong>Throughput</strong><small>Run network tests</small></span></button>
              <button type="button" onClick={() => navigate('/devices')}><FiServer /><span><strong>Devices</strong><small>Inspect Titan status</small></span></button>
              <button type="button" onClick={() => navigate('/test-cases')}><FiPlay /><span><strong>Test Cases</strong><small>Open automation cases</small></span></button>
            </div>
          </article>
        </section>
      </main>
    </div>
  )
}

export default Dashboard
