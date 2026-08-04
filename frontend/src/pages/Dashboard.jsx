import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FiActivity,
  FiArrowDown,
  FiArrowRight,
  FiServer,
  FiWifi,
} from 'react-icons/fi'
import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'
import DashboardCard from '../components/DashboardCard'
import api from '../services/api'
import '../App.css'

function Dashboard() {
  const navigate = useNavigate()

  const [device, setDevice] = useState(null)
  const [deviceLoading, setDeviceLoading] = useState(true)
  const [deviceError, setDeviceError] = useState('')

  const [latestThroughput, setLatestThroughput] = useState(null)
  const [throughputStatus, setThroughputStatus] = useState('idle')

  const loadDeviceStatus = async () => {
    setDeviceLoading(true)
    setDeviceError('')

    try {
      const response = await api.get('/device/status', {
        params: {
          titan_ip: '192.168.100.1',
        },
      })

      setDevice(response.data)
    } catch (requestError) {
      setDevice(null)
      setDeviceError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to load device status.'
      )
    } finally {
      setDeviceLoading(false)
    }
  }

  useEffect(() => {
    loadDeviceStatus()

    const deviceInterval = window.setInterval(
      loadDeviceStatus,
      10000
    )

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
        window.localStorage.removeItem(
          'wncLatestThroughputResult'
        )
      }
    }

    if (storedStatus) {
      setThroughputStatus(storedStatus)
    }

    return () => {
      window.clearInterval(deviceInterval)
    }
  }, [])

  const connectedDeviceCount = device?.reachable ? 1 : 0

  const currentDownload =
    latestThroughput?.download_mbps !== null &&
    latestThroughput?.download_mbps !== undefined
      ? `${latestThroughput.download_mbps} Mbps`
      : '0 Mbps'

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

  const activeTestCount =
    throughputStatus === 'queued' ||
    throughputStatus === 'running'
      ? 1
      : 0

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

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar />

        <section className="dashboard-header">
          <div>
            <h2>Test Overview</h2>
            <p>
              Monitor devices, tests, logs, and network performance.
            </p>
          </div>

          <button
            className="start-test-button"
            type="button"
            onClick={() => navigate('/throughput')}
          >
            Start New Test
          </button>
        </section>

        {deviceError && (
          <div className="api-error-message dashboard-api-error">
            <strong>Dashboard notice:</strong> {deviceError}
          </div>
        )}

        <section className="dashboard-cards">
          <DashboardCard
            title="Connected Devices"
            value={
              deviceLoading
                ? '...'
                : String(connectedDeviceCount)
            }
            subtitle={
              device?.reachable
                ? `Titan 3 at ${device.ip_address}`
                : 'No devices detected'
            }
          />

          <DashboardCard
            title="Active Tests"
            value={String(activeTestCount)}
            subtitle={
              activeTestCount
                ? 'Throughput test is running'
                : 'No test currently running'
            }
          />

          <DashboardCard
            title="Current Throughput"
            value={currentDownload}
            subtitle={
              latestThroughput
                ? `Upload ${currentUpload}`
                : 'Waiting for test data'
            }
          />

          <DashboardCard
            title="QXDM Logs"
            value="0"
            subtitle="No logs captured"
          />
        </section>

        <section className="dashboard-grid">
          <article className="dashboard-panel throughput-panel">
            <div className="panel-header">
              <div>
                <h3>Throughput Monitor</h3>
                <p>
                  Latest download, upload, and ping performance.
                </p>
              </div>

              <span
                className={`status-badge ${throughputBadgeClass}`}
              >
                {throughputBadgeLabel}
              </span>
            </div>

            {latestThroughput ? (
              <div className="dashboard-throughput-results">
                <div className="dashboard-throughput-item">
                  <span className="dashboard-throughput-icon download">
                    <FiArrowDown />
                  </span>

                  <div>
                    <p>Download</p>
                    <strong>{currentDownload}</strong>
                  </div>
                </div>

                <div className="dashboard-throughput-item">
                  <span className="dashboard-throughput-icon upload">
                    <FiActivity />
                  </span>

                  <div>
                    <p>Upload</p>
                    <strong>{currentUpload}</strong>
                  </div>
                </div>

                <div className="dashboard-throughput-item">
                  <span className="dashboard-throughput-icon ping">
                    <FiWifi />
                  </span>

                  <div>
                    <p>Ping</p>
                    <strong>{currentPing}</strong>
                  </div>
                </div>
              </div>
            ) : (
              <div className="empty-state">
                <p>No throughput data available.</p>
                <span>
                  Start a test to begin monitoring.
                </span>
              </div>
            )}

            <button
              type="button"
              className="dashboard-panel-link"
              onClick={() => navigate('/throughput')}
            >
              View Throughput Testing
              <FiArrowRight />
            </button>
          </article>

          <article className="dashboard-panel">
            <div className="panel-header">
              <div>
                <h3>Device Status</h3>
                <p>Current Titan 3 connection information.</p>
              </div>

              <span
                className={`status-badge ${
                  device?.reachable ? 'running' : 'failed'
                }`}
              >
                {deviceLoading
                  ? 'Checking'
                  : device?.reachable
                    ? 'Connected'
                    : 'Disconnected'}
              </span>
            </div>

            <div className="dashboard-device-summary">
              <div className="dashboard-device-icon">
                <FiServer />
              </div>

              <div>
                <h4>Titan 3</h4>
                <p>
                  {device?.ip_address ?? '192.168.100.1'}
                </p>
              </div>
            </div>

            <div className="dashboard-device-details">
              <div>
                <span>Status</span>
                <strong>
                  {device?.status ?? 'Unknown'}
                </strong>
              </div>

              <div>
                <span>Firmware</span>
                <strong>
                  {device?.firmware_version ??
                    'Not available'}
                </strong>
              </div>

              <div>
                <span>Carrier</span>
                <strong>
                  {device?.carrier ?? 'Not available'}
                </strong>
              </div>
            </div>

            <button
              type="button"
              className="dashboard-panel-link"
              onClick={() => navigate('/devices')}
            >
              View Device Details
              <FiArrowRight />
            </button>
          </article>
        </section>
      </main>
    </div>
  )
}

export default Dashboard