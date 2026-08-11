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
import '../App.css'

function Syslog() {
  const [wrapperFolder, setWrapperFolder] = useState('')
  const [status, setStatus] = useState('idle')
  const [notes, setNotes] = useState('')

  const statusLabel =
    status === 'opening'
      ? 'Opening Verizon GUI'
      : status === 'collecting'
        ? 'Collecting'
        : status === 'completed'
          ? 'Completed'
          : 'Idle'

  const handleBrowseWrapper = () => {
    setWrapperFolder(
      'Wrapper folder picker will be connected to the backend.'
    )
  }

  const handleOpenVerizonGui = () => {
    setStatus('opening')
  }

  const handleStartCollection = () => {
    setStatus('collecting')
  }

  const handleSaveSyslog = () => {
    setStatus('completed')
  }

  const handleRefresh = () => {}

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
                  Select the wrapper session before opening the Verizon GUI.
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
                Planned save location: &lt;wrapper&gt;/syslog/. The backend
                will later help set this destination when the Verizon GUI
                Save dialog appears.
              </span>
            </div>

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
                className="qxdm-start-button"
                onClick={handleStartCollection}
              >
                <FiActivity />
                Start Syslog
              </button>

              <button
                type="button"
                className="qxdm-stop-button"
                onClick={handleSaveSyslog}
              >
                <FiSave />
                Save Syslog
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
                ['5. Save', 'Click Save and target the wrapper/syslog folder.'],
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

        <section className="dashboard-panel throughput-history-panel">
          <div className="panel-header">
            <div>
              <h3>Collected Syslog Files</h3>
              <p>
                Generated Verizon GUI syslogs will appear here after backend
                integration.
              </p>
            </div>

            <span className="history-count">0 files</span>
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
                <tr>
                  <td colSpan="5" className="empty-table-message">
                    No syslog files collected yet.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  )
}

export default Syslog