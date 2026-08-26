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

  // Live radio metrics (RSRP, Technology, etc.) come from the Verizon
  // GUI, which is behind a login. The password only ever lives in this
  // component's state and the one-time Connect request body - it is
  // never persisted to localStorage and the backend never stores it,
  // only the resulting session cookie (in memory, per Titan IP).
  const [radioPassword, setRadioPassword] = useState('')
  const [isConnectingRadio, setIsConnectingRadio] = useState(false)

  // In the Electron app, a plain <a target="_blank"> can end up navigating
  // the app's own window instead of opening a real browser tab - the Titan
  // serves a self-signed certificate Electron doesn't trust, so that
  // navigation fails and leaves the app blank. Hand it to the OS browser
  // explicitly when running in Electron; a plain web browser (e.g. the
  // Vercel deployment) doesn't have window.wncTestHub, so the link's
  // normal target="_blank" behavior is left alone there.
  const handleOpenTitanGui = (event) => {
    if (window.wncTestHub?.openExternal) {
      event.preventDefault()
      window.wncTestHub.openExternal(event.currentTarget.href)
    }
  }

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

  const handleConnectRadioMetrics = async (event) => {
    event.preventDefault()

    if (!radioPassword.trim() || isConnectingRadio) {
      return
    }

    setIsConnectingRadio(true)
    setError('')

    try {
      await api.post(
        '/device/radio-metrics/connect',
        {
          titan_ip: titanIp,
          password: radioPassword,
        },
        {
          // Logging in launches a real browser (same as the Syslog
          // page's automation) - the default 10s client timeout isn't
          // enough for a browser launch + page load + login round trip.
          timeout: 0,
        }
      )

      // Don't keep the password around in state longer than it takes to
      // send the one request.
      setRadioPassword('')

      await loadDeviceStatus()
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to connect for live radio metrics.'
      )
    } finally {
      setIsConnectingRadio(false)
    }
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
                onClick={handleOpenTitanGui}
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

            {!device?.radio_metrics_connected && (
              <form
                className="device-ip-form"
                onSubmit={handleConnectRadioMetrics}
              >
                <label className="form-field">
                  <span>Verizon GUI Password</span>

                  <input
                    type="password"
                    value={radioPassword}
                    onChange={(event) =>
                      setRadioPassword(event.target.value)
                    }
                    placeholder="Needed once for live radio metrics"
                    autoComplete="off"
                  />
                </label>

                <button
                  type="submit"
                  className="refresh-device-button"
                  disabled={
                    isConnectingRadio || !radioPassword.trim()
                  }
                >
                  {isConnectingRadio
                    ? 'Connecting...'
                    : 'Connect'}
                </button>
              </form>
            )}

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