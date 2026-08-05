import { useEffect, useMemo, useState } from 'react'
import {
  FiActivity,
  FiBarChart2,
  FiDownload,
  FiRefreshCw,
  FiSearch,
  FiUpload,
  FiZap,
} from 'react-icons/fi'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'
import api from '../services/api'
import '../App.css'

function Analytics() {
  const [summary, setSummary] = useState(null)
  const [history, setHistory] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  const [searchValue, setSearchValue] = useState('')
  const [serverFilter, setServerFilter] = useState('all')
  const [carrierFilter, setCarrierFilter] = useState('all')

  const loadAnalytics = async () => {
    setIsLoading(true)
    setError('')

    try {
      const response = await api.get('/analytics')

      setSummary(response.data?.summary ?? null)
      setHistory(response.data?.history ?? [])
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to retrieve analytics data.'
      )
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadAnalytics()
  }, [])

  const displayMetric = (
    value,
    unit = '',
    fallback = 'Not available'
  ) => {
    if (
      value === null ||
      value === undefined ||
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
      return value
    }

    return parsedDate.toLocaleString()
  }

  const serverOptions = useMemo(() => {
    return [
      ...new Set(
        history
          .map((item) => item.server_name)
          .filter(Boolean)
      ),
    ].sort()
  }, [history])

  const carrierOptions = useMemo(() => {
    return [
      ...new Set(
        history
          .map((item) => item.carrier)
          .filter(Boolean)
      ),
    ].sort()
  }, [history])

  const filteredHistory = useMemo(() => {
    const normalizedSearch = searchValue
      .trim()
      .toLowerCase()

    return history.filter((item) => {
      const matchesServer =
        serverFilter === 'all' ||
        item.server_name === serverFilter

      const matchesCarrier =
        carrierFilter === 'all' ||
        item.carrier === carrierFilter

      const searchableValues = [
        item.timestamp,
        item.titan_ip,
        item.server_name,
        item.server_location,
        item.carrier,
        item.technology,
        item.mode,
        item.notes,
        item.connection_status,
      ]

      const matchesSearch =
        !normalizedSearch ||
        searchableValues.some((value) =>
          String(value ?? '')
            .toLowerCase()
            .includes(normalizedSearch)
        )

      return (
        matchesServer &&
        matchesCarrier &&
        matchesSearch
      )
    })
  }, [
    history,
    searchValue,
    serverFilter,
    carrierFilter,
  ])

  const chartData = useMemo(() => {
    return [...filteredHistory]
      .reverse()
      .map((item, index) => ({
        label: item.timestamp
          ? new Date(item.timestamp).toLocaleTimeString(
              [],
              {
                hour: '2-digit',
                minute: '2-digit',
              }
            )
          : `Run ${index + 1}`,
        download: Number(item.download_mbps) || 0,
        upload: Number(item.upload_mbps) || 0,
        ping: Number(item.ping_ms) || 0,
      }))
  }, [filteredHistory])

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="Analytics" />

        <section className="page-heading">
          <div>
            <h2>Performance Analytics</h2>
            <p>
              Review throughput trends, saved test history, and
              network performance.
            </p>
          </div>

          <button
            type="button"
            className="analytics-refresh-button"
            onClick={loadAnalytics}
            disabled={isLoading}
          >
            <FiRefreshCw
              className={isLoading ? 'spinning' : ''}
            />
            {isLoading ? 'Refreshing...' : 'Refresh Data'}
          </button>
        </section>

        {error && (
          <div className="api-error-message analytics-error">
            <strong>Analytics error:</strong> {error}
          </div>
        )}

        <section className="analytics-summary-grid">
          <article className="analytics-summary-card">
            <div className="analytics-summary-icon download">
              <FiDownload />
            </div>

            <div>
              <p>Average Download</p>
              <h3>
                {displayMetric(
                  summary?.average_download_mbps,
                  ' Mbps'
                )}
              </h3>
              <span>
                Min{' '}
                {displayMetric(
                  summary?.minimum_download_mbps,
                  ' Mbps'
                )}
                {' · '}
                Max{' '}
                {displayMetric(
                  summary?.maximum_download_mbps,
                  ' Mbps'
                )}
              </span>
            </div>
          </article>

          <article className="analytics-summary-card">
            <div className="analytics-summary-icon upload">
              <FiUpload />
            </div>

            <div>
              <p>Average Upload</p>
              <h3>
                {displayMetric(
                  summary?.average_upload_mbps,
                  ' Mbps'
                )}
              </h3>
              <span>
                Min{' '}
                {displayMetric(
                  summary?.minimum_upload_mbps,
                  ' Mbps'
                )}
                {' · '}
                Max{' '}
                {displayMetric(
                  summary?.maximum_upload_mbps,
                  ' Mbps'
                )}
              </span>
            </div>
          </article>

          <article className="analytics-summary-card">
            <div className="analytics-summary-icon ping">
              <FiActivity />
            </div>

            <div>
              <p>Average Ping</p>
              <h3>
                {displayMetric(
                  summary?.average_ping_ms,
                  ' ms'
                )}
              </h3>
              <span>
                Average network latency
              </span>
            </div>
          </article>

          <article className="analytics-summary-card">
            <div className="analytics-summary-icon tests">
              <FiBarChart2 />
            </div>

            <div>
              <p>Total Saved Runs</p>
              <h3>{summary?.total_runs ?? 0}</h3>
              <span>
                Average jitter{' '}
                {displayMetric(
                  summary?.average_jitter_ms,
                  ' ms'
                )}
              </span>
            </div>
          </article>
        </section>

        <section className="analytics-chart-grid">
          <article className="analytics-chart-card">
            <div className="panel-header">
              <div>
                <h3>Throughput Trend</h3>
                <p>
                  Download and upload results across saved test
                  runs.
                </p>
              </div>

              <FiZap />
            </div>

            <div className="analytics-chart-container">
              {chartData.length > 0 ? (
                <ResponsiveContainer
                  width="100%"
                  height={320}
                >
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="label"
                      minTickGap={24}
                    />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="download"
                      name="Download Mbps"
                      stroke="#16a34a"
                      strokeWidth={3}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="upload"
                      name="Upload Mbps"
                      stroke="#7c3aed"
                      strokeWidth={3}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="empty-state analytics-empty-chart">
                  <p>No throughput history available.</p>
                  <span>
                    Complete a throughput test to populate this
                    chart.
                  </span>
                </div>
              )}
            </div>
          </article>

          <article className="analytics-chart-card">
            <div className="panel-header">
              <div>
                <h3>Ping Trend</h3>
                <p>
                  Network latency across saved throughput runs.
                </p>
              </div>
            </div>

            <div className="analytics-chart-container">
              {chartData.length > 0 ? (
                <ResponsiveContainer
                  width="100%"
                  height={320}
                >
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="label"
                      minTickGap={24}
                    />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="ping"
                      name="Ping ms"
                      stroke="#d97706"
                      strokeWidth={3}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="empty-state analytics-empty-chart">
                  <p>No ping history available.</p>
                  <span>
                    Ping results will appear after testing.
                  </span>
                </div>
              )}
            </div>
          </article>
        </section>

        <section className="analytics-history-card">
          <div className="panel-header">
            <div>
              <h3>Test History</h3>
              <p>
                Search and filter all saved throughput results.
              </p>
            </div>

            <span className="history-count">
              {filteredHistory.length} results
            </span>
          </div>

          <div className="analytics-filter-row">
            <label className="analytics-search-field">
              <FiSearch />

              <input
                type="search"
                value={searchValue}
                onChange={(event) =>
                  setSearchValue(event.target.value)
                }
                placeholder="Search device, server, carrier, notes..."
              />
            </label>

            <select
              value={serverFilter}
              onChange={(event) =>
                setServerFilter(event.target.value)
              }
            >
              <option value="all">All servers</option>

              {serverOptions.map((server) => (
                <option key={server} value={server}>
                  {server}
                </option>
              ))}
            </select>

            <select
              value={carrierFilter}
              onChange={(event) =>
                setCarrierFilter(event.target.value)
              }
            >
              <option value="all">All carriers</option>

              {carrierOptions.map((carrier) => (
                <option key={carrier} value={carrier}>
                  {carrier}
                </option>
              ))}
            </select>
          </div>

          <div className="table-container">
            <table className="analytics-history-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Run</th>
                  <th>Titan IP</th>
                  <th>Download</th>
                  <th>Upload</th>
                  <th>Ping</th>
                  <th>Jitter</th>
                  <th>Server</th>
                  <th>Carrier</th>
                  <th>Status</th>
                </tr>
              </thead>

              <tbody>
                {filteredHistory.length === 0 ? (
                  <tr>
                    <td
                      colSpan="10"
                      className="empty-table-message"
                    >
                      No saved test results match the selected
                      filters.
                    </td>
                  </tr>
                ) : (
                  filteredHistory.map((item, index) => (
                    <tr
                      key={`${item.workbook_path}-${item.run_number}-${index}`}
                    >
                      <td>
                        {formatDate(item.timestamp)}
                      </td>
                      <td>{item.run_number ?? '—'}</td>
                      <td>{item.titan_ip ?? '—'}</td>
                      <td>
                        {displayMetric(
                          item.download_mbps,
                          ' Mbps',
                          '—'
                        )}
                      </td>
                      <td>
                        {displayMetric(
                          item.upload_mbps,
                          ' Mbps',
                          '—'
                        )}
                      </td>
                      <td>
                        {displayMetric(
                          item.ping_ms,
                          ' ms',
                          '—'
                        )}
                      </td>
                      <td>
                        {displayMetric(
                          item.ping_jitter_ms,
                          ' ms',
                          '—'
                        )}
                      </td>
                      <td>
                        <strong>
                          {item.server_name ?? '—'}
                        </strong>
                        <span className="analytics-table-secondary">
                          {item.server_location ?? ''}
                        </span>
                      </td>
                      <td>{item.carrier ?? '—'}</td>
                      <td>
                        <span
                          className={`table-status ${
                            item.connection_status ===
                            'connected'
                              ? 'completed'
                              : 'failed'
                          }`}
                        >
                          {item.connection_status ??
                            'Unknown'}
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

export default Analytics