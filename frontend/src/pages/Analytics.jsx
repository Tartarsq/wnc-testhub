import { useEffect, useMemo, useState } from 'react'
import {
  FiActivity,
  FiBarChart2,
  FiCalendar,
  FiDownload,
  FiEye,
  FiFilter,
  FiRefreshCw,
  FiSearch,
  FiUpload,
  FiX,
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
  const [technologyFilter, setTechnologyFilter] = useState('all')
  const [titanFilter, setTitanFilter] = useState('all')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [selectedResult, setSelectedResult] = useState(null)

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



  const technologyOptions = useMemo(() => {
    return [
      ...new Set(
        history
          .map((item) => item.technology)
          .filter(Boolean)
      ),
    ].sort()
  }, [history])

  const titanOptions = useMemo(() => {
    return [
      ...new Set(
        history
          .map((item) => item.titan_ip)
          .filter(Boolean)
      ),
    ].sort()
  }, [history])

  const filteredHistory = useMemo(() => {
    const normalizedSearch = searchValue
      .trim()
      .toLowerCase()

    const startBoundary = startDate ? new Date(`${startDate}T00:00:00`) : null
    const endBoundary = endDate ? new Date(`${endDate}T23:59:59`) : null

    return history.filter((item) => {
      const itemDate = item.timestamp ? new Date(item.timestamp) : null

      const matchesStartDate =
        !startBoundary ||
        (itemDate && !Number.isNaN(itemDate.getTime()) && itemDate >= startBoundary)

      const matchesEndDate =
        !endBoundary ||
        (itemDate && !Number.isNaN(itemDate.getTime()) && itemDate <= endBoundary)

      const matchesServer =
        serverFilter === 'all' ||
        item.server_name === serverFilter

      const matchesCarrier =
        carrierFilter === 'all' ||
        item.carrier === carrierFilter

      const matchesTechnology =
        technologyFilter === 'all' ||
        item.technology === technologyFilter

      const matchesTitan =
        titanFilter === 'all' ||
        item.titan_ip === titanFilter

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
        matchesStartDate &&
        matchesEndDate &&
        matchesServer &&
        matchesCarrier &&
        matchesTechnology &&
        matchesTitan &&
        matchesSearch
      )
    })
  }, [
    history,
    searchValue,
    serverFilter,
    carrierFilter,
    technologyFilter,
    titanFilter,
    startDate,
    endDate,
  ])


  const filteredSummary = useMemo(() => {
    const valuesFor = (field) =>
      filteredHistory
        .map((item) => Number(item[field]))
        .filter((value) => Number.isFinite(value))

    const downloads = valuesFor('download_mbps')
    const uploads = valuesFor('upload_mbps')
    const pings = valuesFor('ping_ms')
    const jitters = valuesFor('ping_jitter_ms')

    const average = (values) =>
      values.length
        ? values.reduce((sum, value) => sum + value, 0) / values.length
        : null

    return {
      total_runs: filteredHistory.length,
      average_download_mbps: average(downloads),
      minimum_download_mbps: downloads.length ? Math.min(...downloads) : null,
      maximum_download_mbps: downloads.length ? Math.max(...downloads) : null,
      average_upload_mbps: average(uploads),
      minimum_upload_mbps: uploads.length ? Math.min(...uploads) : null,
      maximum_upload_mbps: uploads.length ? Math.max(...uploads) : null,
      average_ping_ms: average(pings),
      average_jitter_ms: average(jitters),
    }
  }, [filteredHistory])

  // Always derive the visible summary from the actual history rows.
  // This guarantees that if 5 Speedtest rows were imported, Analytics
  // displays 5 runs instead of relying on a stale/older backend summary.
  const visibleSummary = filteredSummary

  const chartData = useMemo(() => {
    return [...filteredHistory]
      .reverse()
      .map((item, index) => ({
        label: item.timestamp
          ? `${new Date(item.timestamp).toLocaleTimeString(
              [],
              {
                hour: '2-digit',
                minute: '2-digit',
              }
            )} · Run ${item.run_number ?? index + 1}`
          : `Run ${item.run_number ?? index + 1}`,
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
                  visibleSummary?.average_download_mbps,
                  ' Mbps'
                )}
              </h3>
              <span>
                Min{' '}
                {displayMetric(
                  visibleSummary?.minimum_download_mbps,
                  ' Mbps'
                )}
                {' · '}
                Max{' '}
                {displayMetric(
                  visibleSummary?.maximum_download_mbps,
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
                  visibleSummary?.average_upload_mbps,
                  ' Mbps'
                )}
              </h3>
              <span>
                Min{' '}
                {displayMetric(
                  visibleSummary?.minimum_upload_mbps,
                  ' Mbps'
                )}
                {' · '}
                Max{' '}
                {displayMetric(
                  visibleSummary?.maximum_upload_mbps,
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
                  visibleSummary?.average_ping_ms,
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
              <p>Test Runs</p>
              <h3>{visibleSummary?.total_runs ?? 0}</h3>
              <span>
                Average jitter{' '}
                {displayMetric(
                  visibleSummary?.average_jitter_ms,
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
              {filteredHistory.length}{' '}
              {filteredHistory.length === 1 ? 'test' : 'tests'}
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

            <select
              value={technologyFilter}
              onChange={(event) =>
                setTechnologyFilter(event.target.value)
              }
            >
              <option value="all">All technologies</option>
              {technologyOptions.map((technology) => (
                <option key={technology} value={technology}>
                  {technology}
                </option>
              ))}
            </select>

            <select
              value={titanFilter}
              onChange={(event) =>
                setTitanFilter(event.target.value)
              }
            >
              <option value="all">All Titan devices</option>
              {titanOptions.map((titanIp) => (
                <option key={titanIp} value={titanIp}>
                  {titanIp}
                </option>
              ))}
            </select>

            <label className="analytics-date-field">
              <FiCalendar />
              <input
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
                aria-label="Start date"
              />
            </label>

            <label className="analytics-date-field">
              <FiCalendar />
              <input
                type="date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
                aria-label="End date"
              />
            </label>
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
                  <th>Details</th>
                </tr>
              </thead>

              <tbody>
                {filteredHistory.length === 0 ? (
                  <tr>
                    <td
                      colSpan="11"
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
                      <td>
                        <button
                          type="button"
                          className="analytics-details-button"
                          onClick={() => setSelectedResult(item)}
                        >
                          <FiEye />
                          View
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        {selectedResult && (
          <div
            className="analytics-modal-backdrop"
            onClick={() => setSelectedResult(null)}
          >
            <section
              className="analytics-details-modal"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="analytics-modal-header">
                <div>
                  <h3>Throughput Run Details</h3>
                  <p>{formatDate(selectedResult.timestamp)}</p>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedResult(null)}
                  aria-label="Close details"
                >
                  <FiX />
                </button>
              </div>

              <dl className="analytics-details-grid">
                <div><dt>Run</dt><dd>{selectedResult.run_number ?? '—'}</dd></div>
                <div><dt>Titan IP</dt><dd>{selectedResult.titan_ip ?? '—'}</dd></div>
                <div><dt>Download</dt><dd>{displayMetric(selectedResult.download_mbps, ' Mbps')}</dd></div>
                <div><dt>Upload</dt><dd>{displayMetric(selectedResult.upload_mbps, ' Mbps')}</dd></div>
                <div><dt>Ping</dt><dd>{displayMetric(selectedResult.ping_ms, ' ms')}</dd></div>
                <div><dt>Jitter</dt><dd>{displayMetric(selectedResult.ping_jitter_ms, ' ms')}</dd></div>
                <div><dt>Server</dt><dd>{selectedResult.server_name ?? '—'}</dd></div>
                <div><dt>Carrier</dt><dd>{selectedResult.carrier ?? '—'}</dd></div>
                <div><dt>Technology</dt><dd>{selectedResult.technology ?? '—'}</dd></div>
                <div><dt>Mode</dt><dd>{selectedResult.mode ?? '—'}</dd></div>
                <div className="analytics-details-wide"><dt>Workbook</dt><dd>{selectedResult.workbook_path ?? '—'}</dd></div>
                <div className="analytics-details-wide"><dt>Notes</dt><dd>{selectedResult.notes || 'No notes saved.'}</dd></div>
              </dl>
            </section>
          </div>
        )}
      </main>
    </div>
  )
}

export default Analytics