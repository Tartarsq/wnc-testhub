import { useEffect, useState } from 'react'
import {
  FiActivity,
  FiArrowLeft,
  FiDownload,
  FiExternalLink,
  FiFileText,
  FiMapPin,
  FiRadio,
  FiServer,
  FiUpload,
  FiWifi,
} from 'react-icons/fi'
import { useNavigate, useParams } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'
import api from '../services/api'
import '../App.css'

function TestResultDetails() {
  const navigate = useNavigate()
  const { resultIndex } = useParams()

  const [result, setResult] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const loadResult = async () => {
      setIsLoading(true)
      setError('')

      try {
        const response = await api.get('/analytics')
        const history = response.data?.history ?? []
        const parsedIndex = Number(resultIndex)

        if (
          !Number.isInteger(parsedIndex) ||
          parsedIndex < 0 ||
          parsedIndex >= history.length
        ) {
          throw new Error('The selected test result was not found.')
        }

        setResult(history[parsedIndex])
      } catch (requestError) {
        setError(
          requestError.response?.data?.detail ||
            requestError.message ||
            'Unable to retrieve the test result.'
        )
      } finally {
        setIsLoading(false)
      }
    }

    loadResult()
  }, [resultIndex])

  const displayValue = (value, fallback = 'Not available') => {
    if (value === null || value === undefined || value === '') {
      return fallback
    }

    return String(value)
  }

  const displayMetric = (
    value,
    unit = '',
    fallback = 'Not available'
  ) => {
    if (
      value === null ||
      value === undefined ||
      value === '' ||
      Number.isNaN(Number(value))
    ) {
      return fallback
    }

    return `${Number(value).toFixed(2)}${unit}`
  }

  const formatDate = (value) => {
    if (!value) {
      return 'Not available'
    }

    const parsedDate = new Date(value)

    if (Number.isNaN(parsedDate.getTime())) {
      return String(value)
    }

    return parsedDate.toLocaleString()
  }

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="Test Result Details" />

        <section className="result-details-heading">
          <div>
            <button
              type="button"
              className="result-back-button"
              onClick={() => navigate('/analytics')}
            >
              <FiArrowLeft />
              Back to Analytics
            </button>

            <h2>Throughput Test Report</h2>
            <p>
              Review network performance, radio conditions, and
              saved test artifacts.
            </p>
          </div>

          {result && (
            <span
              className={`status-badge ${
                result.connection_status === 'connected'
                  ? 'running'
                  : 'failed'
              }`}
            >
              {displayValue(result.connection_status, 'Unknown')}
            </span>
          )}
        </section>

        {isLoading && (
          <section className="result-loading-card">
            <div className="spinning result-loading-spinner" />
            <p>Loading test result...</p>
          </section>
        )}

        {error && (
          <div className="api-error-message result-details-error">
            <strong>Result error:</strong> {error}
          </div>
        )}

        {result && !isLoading && (
          <>
            <section className="result-hero-card">
              <div className="result-hero-main">
                <span>Test completed</span>
                <h3>{formatDate(result.timestamp)}</h3>
                <p>
                  Run {displayValue(result.run_number, '—')} · Titan{' '}
                  {displayValue(result.titan_ip, '—')}
                </p>
              </div>

              <div className="result-hero-server">
                <FiServer />
                <div>
                  <span>Speedtest Server</span>
                  <strong>
                    {displayValue(result.server_name, 'Unknown server')}
                  </strong>
                  <p>
                    {displayValue(
                      result.server_location,
                      'Location unavailable'
                    )}
                  </p>
                </div>
              </div>
            </section>

            <section className="result-metrics-grid">
              <article className="result-metric-card download">
                <FiDownload />
                <div>
                  <span>Download</span>
                  <strong>
                    {displayMetric(result.download_mbps, ' Mbps')}
                  </strong>
                </div>
              </article>

              <article className="result-metric-card upload">
                <FiUpload />
                <div>
                  <span>Upload</span>
                  <strong>
                    {displayMetric(result.upload_mbps, ' Mbps')}
                  </strong>
                </div>
              </article>

              <article className="result-metric-card ping">
                <FiActivity />
                <div>
                  <span>Ping</span>
                  <strong>
                    {displayMetric(result.ping_ms, ' ms')}
                  </strong>
                </div>
              </article>

              <article className="result-metric-card jitter">
                <FiWifi />
                <div>
                  <span>Jitter</span>
                  <strong>
                    {displayMetric(result.ping_jitter_ms, ' ms')}
                  </strong>
                </div>
              </article>
            </section>

            <section className="result-details-layout">
              <article className="result-details-card">
                <div className="result-section-heading">
                  <FiRadio />
                  <div>
                    <h3>Cellular and Radio Information</h3>
                    <p>
                      Device mode and RF measurements captured during
                      the run.
                    </p>
                  </div>
                </div>

                <dl className="result-details-list">
                  <div>
                    <dt>Carrier</dt>
                    <dd>{displayValue(result.carrier)}</dd>
                  </div>
                  <div>
                    <dt>Technology</dt>
                    <dd>{displayValue(result.technology)}</dd>
                  </div>
                  <div>
                    <dt>Mode</dt>
                    <dd>{displayValue(result.mode)}</dd>
                  </div>
                  <div>
                    <dt>Serving Band</dt>
                    <dd>{displayValue(result.serving_band)}</dd>
                  </div>
                  <div>
                    <dt>RSRP</dt>
                    <dd>{displayMetric(result.rsrp_dbm, ' dBm')}</dd>
                  </div>
                  <div>
                    <dt>RSSI</dt>
                    <dd>{displayMetric(result.rssi_dbm, ' dBm')}</dd>
                  </div>
                  <div>
                    <dt>SINR</dt>
                    <dd>{displayMetric(result.sinr_db, ' dB')}</dd>
                  </div>
                  <div>
                    <dt>Firmware</dt>
                    <dd>{displayValue(result.firmware_version)}</dd>
                  </div>
                </dl>
              </article>

              <article className="result-details-card">
                <div className="result-section-heading">
                  <FiMapPin />
                  <div>
                    <h3>Network and Test Information</h3>
                    <p>
                      Connection, server, interface, and timing details.
                    </p>
                  </div>
                </div>

                <dl className="result-details-list">
                  <div>
                    <dt>ISP</dt>
                    <dd>{displayValue(result.isp)}</dd>
                  </div>
                  <div>
                    <dt>External IP</dt>
                    <dd>{displayValue(result.external_ip)}</dd>
                  </div>
                  <div>
                    <dt>Interface</dt>
                    <dd>{displayValue(result.interface_name)}</dd>
                  </div>
                  <div>
                    <dt>Packet Loss</dt>
                    <dd>
                      {displayMetric(result.packet_loss_percent, '%')}
                    </dd>
                  </div>
                  <div>
                    <dt>Test Duration</dt>
                    <dd>
                      {displayMetric(
                        result.test_duration_seconds,
                        ' seconds'
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>Connection Status</dt>
                    <dd>{displayValue(result.connection_status)}</dd>
                  </div>
                </dl>

                {result.result_url && (
                  <a
                    className="result-external-link"
                    href={result.result_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <FiExternalLink />
                    Open Speedtest Result
                  </a>
                )}
              </article>
            </section>

            <section className="result-artifacts-card">
              <div className="result-section-heading">
                <FiFileText />
                <div>
                  <h3>Saved Artifacts and Notes</h3>
                  <p>
                    Files and diagnostic information associated with
                    this run.
                  </p>
                </div>
              </div>

              <dl className="result-artifacts-list">
                <div>
                  <dt>Workbook</dt>
                  <dd>{displayValue(result.workbook_path)}</dd>
                </div>
                <div>
                  <dt>Session Folder</dt>
                  <dd>{displayValue(result.session_folder)}</dd>
                </div>
                <div>
                  <dt>Notes</dt>
                  <dd>
                    {displayValue(result.notes, 'No notes were saved.')}
                  </dd>
                </div>
                <div>
                  <dt>Metrics Error</dt>
                  <dd>
                    {displayValue(
                      result.metrics_error,
                      'No metrics error was recorded.'
                    )}
                  </dd>
                </div>
              </dl>
            </section>
          </>
        )}
      </main>
    </div>
  )
}

export default TestResultDetails