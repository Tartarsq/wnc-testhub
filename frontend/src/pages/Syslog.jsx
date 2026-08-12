import { useState } from 'react'
import {
  FiActivity,
  FiCheckCircle,
  FiFileText,
  FiFolder,
  FiPlay,
  FiRefreshCw,
  FiSave,
} from 'react-icons/fi'
import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'
import api from '../services/api'
import '../App.css'

function Syslog() {
  const [wrapperFolder, setWrapperFolder] = useState('')
  const [status, setStatus] = useState('idle')
  const [notes, setNotes] = useState('')
  const [titanIp, setTitanIp] = useState('192.168.100.1')
  const [syslogFolder, setSyslogFolder] = useState('')
  const [error, setError] = useState('')
  const [syslogFiles, setSyslogFiles] = useState([])
  const [message, setMessage] = useState('')

  const statusLabel =
    status === 'opening'
      ? 'Opening Verizon GUI'
      : status === 'collecting'
        ? 'Collecting'
        : status === 'completed'
          ? 'Completed'
          : 'Idle'

  const handleBrowseWrapper = async () => {
    setError('')

    try {
      const response = await api.get(
        '/syslog/verizon/browse-wrapper',
        { timeout: 0 }
      )

      if (response.data?.path) {
        setWrapperFolder(response.data.path)
        setSyslogFolder(response.data.syslog_folder ?? '')
        setMessage(
          `Syslog destination: ${response.data.syslog_folder ?? ''}`
        )
        setError('')
      }
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to select the wrapper session.'
      )
    }
  }

  const handleOpenVerizonGui = async () => {
    if (!wrapperFolder.trim()) {
      setError('Select the wrapper session first.')
      return
    }

    setError('')
    setStatus('opening')

    try {
      const response = await api.post(
        '/syslog/verizon/open',
        {
          wrapper_session_folder: wrapperFolder.trim(),
          titan_ip: titanIp.trim(),
        },
        { timeout: 0 }
      )

      setStatus('collecting')
      setSyslogFolder(
        response.data?.syslog_folder ?? ''
      )
    } catch (requestError) {
      setStatus('idle')
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to open the Verizon GUI.'
      )
    }
  }

  const handleSaveSyslog = async () => {
    if (!syslogFolder) {
      setError('Open the Verizon GUI with a wrapper session first.')
      return
    }

    try {
      await api.get(
        '/syslog/verizon/open-folder',
        {
          params: {
            syslog_folder: syslogFolder,
          },
        }
      )
      setStatus('completed')
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to open the syslog output folder.'
      )
    }
  }

  const handleDetectSavedSyslog = async () => {
    if (!syslogFolder) {
      setError('Select a wrapper and open the Verizon GUI first.')
      return
    }

    setError('')
    setMessage('Checking the wrapper syslog folder...')

    try {
      const response = await api.get(
        '/syslog/verizon/files',
        {
          params: {
            syslog_folder: syslogFolder,
          },
        }
      )
      const files = response.data?.files ?? []

      setSyslogFiles(files)
      setMessage(response.data?.message ?? '')

      if (files.length > 0) {
        setStatus('completed')
      }
    } catch (requestError) {
      setMessage('')
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to detect the saved syslog.'
      )
    }
  }

  const handleRefresh = async () => {
    try {
      const response = await api.get('/syslog/verizon/status')

      if (response.data?.syslog_folder) {
        setSyslogFolder(response.data.syslog_folder)
      }

      if (response.data?.titan_ip) {
        setTitanIp(response.data.titan_ip)
      }

      if (response.data?.syslog_folder) {
        const filesResponse = await api.get(
          '/syslog/verizon/files',
          {
            params: {
              syslog_folder:
                response.data.syslog_folder,
            },
          }
        )
        setSyslogFiles(filesResponse.data?.files ?? [])
      }
    } catch {
      // Keep page usable if backend is not running.
    }
  }

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="Syslog" />

        <section className="page-heading">
          <div>
            <h2>Verizon GUI Syslog Collection</h2>
            <p>
              Open the Verizon GUI, navigate to Diagnostic Monitoring and
              System Logging, save the syslog, and keep it with the selected
              WNC TestHub wrapper session.
            </p>
          </div>

          <span className="status-badge idle">
            {statusLabel}
          </span>
        </section>

        <section className="qxdm-status-grid">
          <article className="qxdm-status-card">
            <div className="qxdm-status-icon">
              <FiActivity />
            </div>
            <div>
              <p>Verizon GUI</p>
              <h3>
                {status === 'opening' ||
                status === 'collecting' ||
                status === 'completed'
                  ? 'Ready'
                  : 'Not Open'}
              </h3>
              <span>Backend launch detection will be added next.</span>
            </div>
          </article>

          <article className="qxdm-status-card">
            <div className="qxdm-status-icon logging">
              <FiFileText />
            </div>
            <div>
              <p>System Logging</p>
              <h3>{statusLabel}</h3>
              <span>Diagnostic Monitoring → System Logging</span>
            </div>
          </article>

          <article className="qxdm-status-card">
            <div className="qxdm-status-icon process">
              <FiFolder />
            </div>
            <div>
              <p>Wrapper Destination</p>
              <h3>{wrapperFolder ? 'Selected' : 'Not Selected'}</h3>
              <span>
                Syslog files will be stored under wrapper/syslog.
              </span>
            </div>
          </article>
        </section>

        <section className="qxdm-layout-grid">
          <article className="qxdm-control-card">
            <div className="section-heading">
              <div className="section-icon">
                <FiFileText />
              </div>

              <div>
                <h3>Syslog Configuration</h3>
                <p>
                  Select the wrapper session and Titan IP before opening the Verizon GUI.
                </p>
              </div>
            </div>

            <div className="qxdm-form-grid">
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
                </div>

                <small className="qxdm-session-help">
                  Select the wrapper session root folder. TestHub will use
                  its syslog subfolder as the target save location.
                </small>
              </label>

              <label className="form-field">
                <span>Titan IP</span>

                <input
                  type="text"
                  value={titanIp}
                  onChange={(event) =>
                    setTitanIp(event.target.value)
                  }
                  placeholder="192.168.100.1"
                />

                <small className="qxdm-session-help">
                  Open Verizon GUI at https://&lt;Titan-IP&gt;/#/login/
                </small>
              </label>

              <label className="form-field">
                <span>Notes</span>

                <input
                  type="text"
                  value={notes}
                  onChange={(event) =>
                    setNotes(event.target.value)
                  }
                  placeholder="Optional syslog notes"
                />
              </label>
            </div>

            <div className="configuration-note">
              <FiSave />
              <span>
                Save the Verizon GUI syslog manually into the folder shown below. TestHub looks for messages_SYS.log, messages_SYS(1).log, messages_SYS(2).log, and the same numbered pattern. After saving, click Detect Saved Syslog.
              </span>
            </div>

            {syslogFolder && (
              <div className="qxdm-manual-settings-banner">
                <strong>Syslog Save Folder</strong>
                <span>{syslogFolder}</span>
              </div>
            )}

            {error && (
              <div className="api-error-message">
                <strong>Syslog error:</strong> {error}
              </div>
            )}

            <div className="qxdm-action-row">
              <button
                type="button"
                className="qxdm-start-button"
                onClick={handleOpenVerizonGui}
              >
                <FiPlay />
                Open Verizon GUI
              </button>

              <button
                type="button"
                className="qxdm-stop-button"
                onClick={handleSaveSyslog}
              >
                <FiSave />
                Open Syslog Folder
              </button>

              <button
                type="button"
                className="qxdm-start-button"
                onClick={handleDetectSavedSyslog}
              >
                <FiCheckCircle />
                Detect Saved Syslog
              </button>

              <button
                type="button"
                className="qxdm-refresh-button"
                onClick={handleRefresh}
              >
                <FiRefreshCw />
                Refresh
              </button>
            </div>
          </article>

          <article className="qxdm-monitor-card">
            <div className="panel-header">
              <div>
                <h3>Verizon GUI Workflow</h3>
                <p>
                  Exact manual path we will automate or assist with next.
                </p>
              </div>

              <FiFileText />
            </div>

            <div className="wrapper-progress-list">
              {[
                ['1. Select Wrapper Session', 'Choose the wrapper that should receive the syslog.'],
                ['2. Open Verizon GUI', 'Launch or focus the Verizon diagnostic application.'],
                ['3. Diagnostic Monitoring', 'Navigate to Diagnostic Monitoring.'],
                ['4. System Logging', 'Open the System Logging section.'],
                ['5. Save', 'Click Save and target the displayed wrapper/syslog folder.'],
                ['6. Detect Saved Syslog', 'Return to TestHub and confirm the file was detected.'],
              ].map(([title, detail]) => (
                <div className="wrapper-progress-item" key={title}>
                  <FiCheckCircle />
                  <div>
                    <strong>{title}</strong>
                    <span>{detail}</span>
                  </div>
                </div>
              ))}
            </div>
          </article>
        </section>

        {message && (
          <div className="qxdm-manual-settings-banner">
            <strong>Syslog Status</strong>
            <span>{message}</span>
          </div>
        )}

        <section className="dashboard-panel throughput-history-panel">
          <div className="panel-header">
            <div>
              <h3>Collected Syslog Files</h3>
              <p>
                Detected Verizon GUI messages_SYS*.log files from the selected wrapper
                will appear here.
              </p>
            </div>

            <span className="history-count">
              {syslogFiles.length}{' '}
              {syslogFiles.length === 1 ? 'file' : 'files'}
            </span>
          </div>

          <div className="table-container">
            <table className="throughput-table">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Created</th>
                  <th>Size</th>
                  <th>Wrapper Location</th>
                  <th>Status</th>
                </tr>
              </thead>

              <tbody>
                {syslogFiles.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="empty-table-message">
                      No messages_SYS*.log files detected in the wrapper or Downloads yet.
                    </td>
                  </tr>
                ) : (
                  syslogFiles.map((file) => (
                    <tr key={file.path}>
                      <td>{file.filename}</td>
                      <td>{file.modified_at ?? 'Unknown'}</td>
                      <td>
                        {file.size_bytes != null
                          ? `${(file.size_bytes / 1024).toFixed(1)} KB`
                          : 'Unknown'}
                      </td>
                      <td>{file.path}</td>
                      <td>
                        <span className="table-status completed">
                          Detected
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

export default Syslog