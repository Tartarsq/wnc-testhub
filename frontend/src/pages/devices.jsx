import { useEffect, useState } from 'react'
import {
  FiExternalLink,
  FiRefreshCw,
  FiServer,
  FiWifi,
} from 'react-icons/fi'
import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'
import api from '../services/api'
import '../App.css'

function Devices() {
  const [titanIp, setTitanIp] = useState('192.168.100.1')
  const [device, setDevice] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  const loadDeviceStatus = async () => {
    setIsLoading(true)
    setError('')

    try {
      const response = await api.get('/device/status', {
        params: {
          titan_ip: titanIp,
        },
      })

      setDevice(response.data)
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to retrieve Titan device status.'
      )
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadDeviceStatus()

    const interval = window.setInterval(
      loadDeviceStatus,
      10000
    )

    return () => {
      window.clearInterval(interval)
    }
  }, [])

  const handleSubmit = (event) => {
    event.preventDefault()
    loadDeviceStatus()
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

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="Devices" />

        <section className="page-heading">
          <div>
            <h2>Titan 3 Device</h2>
            <p>
              Monitor the connection and device information from the
              backend.
            </p>
          </div>

          <span
            className={`status-badge ${
              device?.reachable ? 'running' : 'failed'
            }`}
          >
            {isLoading
              ? 'Checking'
              : device?.reachable
                ? 'Connected'
                : 'Disconnected'}
          </span>
        </section>

        <section className="device-control-panel">
          <form
            className="device-ip-form"
            onSubmit={handleSubmit}
          >
            <label className="form-field">
              <span>Titan IP Address</span>

              <input
                type="text"
                value={titanIp}
                onChange={(event) =>
                  setTitanIp(event.target.value)
                }
              />
            </label>

            <button
              type="submit"
              className="refresh-device-button"
              disabled={isLoading}
            >
              <FiRefreshCw
                className={isLoading ? 'spinning' : ''}
              />

              {isLoading ? 'Checking...' : 'Refresh Status'}
            </button>
          </form>
        </section>

        {error && (
          <div className="api-error-message">
            <strong>Device error:</strong> {error}
          </div>
        )}

        <section className="device-overview-grid">
          <article className="device-primary-card">
            <div className="device-card-header">
              <div className="device-icon">
                <FiServer />
              </div>

              <div>
                <h3>Titan 3</h3>
                <p>{device?.ip_address ?? titanIp}</p>
              </div>

              <span
                className={`device-connection-indicator ${
                  device?.reachable
                    ? 'connected'
                    : 'disconnected'
                }`}
              >
                <FiWifi />

                {device?.reachable
                  ? 'Connected'
                  : 'Disconnected'}
              </span>
            </div>

            <div className="device-summary-grid">
              <div>
                <span>Status</span>
                <strong>
                  {displayValue(device?.status)}
                </strong>
              </div>

              <div>
                <span>IP Address</span>
                <strong>
                  {displayValue(device?.ip_address)}
                </strong>
              </div>

              <div>
                <span>Firmware</span>
                <strong>
                  {displayValue(device?.firmware_version)}
                </strong>
              </div>

              <div>
                <span>Carrier</span>
                <strong>
                  {displayValue(device?.carrier)}
                </strong>
              </div>
            </div>

            {device?.gui_url && (
              <a
                className="open-device-gui-button"
                href={device.gui_url}
                target="_blank"
                rel="noreferrer"
              >
                <FiExternalLink />
                Open Titan Web GUI
              </a>
            )}
          </article>

          <article className="dashboard-panel device-network-panel">
            <div className="panel-header">
              <div>
                <h3>Network Information</h3>
                <p>
                  Current cellular and radio information.
                </p>
              </div>
            </div>

            <dl className="device-details-list">
              <div>
                <dt>Technology</dt>
                <dd>{displayValue(device?.technology)}</dd>
              </div>

              <div>
                <dt>Mode</dt>
                <dd>{displayValue(device?.mode)}</dd>
              </div>

              <div>
                <dt>Serving Band</dt>
                <dd>
                  {displayValue(device?.serving_band)}
                </dd>
              </div>

              <div>
                <dt>RSRP</dt>
                <dd>
                  {device?.rsrp_dbm !== null &&
                  device?.rsrp_dbm !== undefined
                    ? `${device.rsrp_dbm} dBm`
                    : 'Not available'}
                </dd>
              </div>

              <div>
                <dt>RSSI</dt>
                <dd>
                  {device?.rssi_dbm !== null &&
                  device?.rssi_dbm !== undefined
                    ? `${device.rssi_dbm} dBm`
                    : 'Not available'}
                </dd>
              </div>

              <div>
                <dt>SINR</dt>
                <dd>
                  {device?.sinr_db !== null &&
                  device?.sinr_db !== undefined
                    ? `${device.sinr_db} dB`
                    : 'Not available'}
                </dd>
              </div>
            </dl>
          </article>
        </section>

        {device?.metrics_error && (
          <div className="device-warning-message">
            <strong>Metrics notice:</strong>{' '}
            {device.metrics_error}
          </div>
        )}
      </main>
    </div>
  )
}

export default Devices