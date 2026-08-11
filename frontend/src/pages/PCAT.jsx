


import { useState } from 'react'
import {
  FiActivity,
  FiCheckCircle,
  FiFolder,
  FiHardDrive,
  FiPlay,
  FiRefreshCw,
  FiServer,
  FiTerminal,
} from 'react-icons/fi'
import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'
import '../App.css'

function PCAT() {
  const [wrapperFolder, setWrapperFolder] = useState('')
  const [adbFolder, setAdbFolder] = useState('')
  const [downloadModeResult, setDownloadModeResult] = useState('')
  const [status, setStatus] = useState('idle')

  const handleBrowseWrapper = () => {
    setWrapperFolder(
      'Wrapper folder picker will be connected to the backend.'
    )
  }

  const handleBrowseAdb = () => {
    setAdbFolder(
      'ADB/platform-tools picker will be connected to the backend.'
    )
  }

  const handleCheckDownloadMode = () => {
    setDownloadModeResult(
      'Backend will run: adb shell cat /sys/module/qcom_dload_mode/parameters/download_mode'
    )
  }

  const handleEnableRamdump = () => {
    setStatus('enabled')
  }

  const handleOpenPcat = () => {
    setStatus('pcat-open')
  }

  const handleRefresh = () => {}

  const statusLabel =
    status === 'enabled'
      ? 'RAM Dump Enabled'
      : status === 'pcat-open'
        ? 'PCAT Open'
        : 'Idle'

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="PCAT" />

        <section className="page-heading">
          <div>
            <h2>PCAT RAM Dump</h2>
            <p>
              Prepare RAM dump mode using ADB, open PCAT, and keep dump
              artifacts organized under the selected wrapper session.
            </p>
          </div>

          <span className="status-badge idle">
            {statusLabel}
          </span>
        </section>

        <section className="qxdm-status-grid">
          <article className="qxdm-status-card">
            <div className="qxdm-status-icon">
              <FiTerminal />
            </div>
            <div>
              <p>ADB</p>
              <h3>{adbFolder ? 'Configured' : 'Not Configured'}</h3>
              <span>platform-tools / adb.exe location</span>
            </div>
          </article>

          <article className="qxdm-status-card">
            <div className="qxdm-status-icon process">
              <FiHardDrive />
            </div>
            <div>
              <p>RAM Dump</p>
              <h3>{statusLabel}</h3>
              <span>ADB preparation + PCAT workflow</span>
            </div>
          </article>

          <article className="qxdm-status-card">
            <div className="qxdm-status-icon logging">
              <FiFolder />
            </div>
            <div>
              <p>Wrapper Destination</p>
              <h3>{wrapperFolder ? 'Selected' : 'Not Selected'}</h3>
              <span>PCAT artifacts will be stored under wrapper/pcat.</span>
            </div>
          </article>
        </section>

        <section className="qxdm-layout-grid">
          <article className="qxdm-control-card">
            <div className="section-heading">
              <div className="section-icon">
                <FiTerminal />
              </div>

              <div>
                <h3>RAM Dump Preparation</h3>
                <p>
                  Configure ADB, run the two required commands, then continue
                  in PCAT.
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
              </label>

              <label className="form-field qxdm-folder-field">
                <span>ADB / platform-tools Folder</span>

                <div className="qxdm-folder-input">
                  <FiFolder />

                  <input
                    type="text"
                    value={adbFolder}
                    onChange={(event) =>
                      setAdbFolder(event.target.value)
                    }
                    placeholder="Folder containing adb.exe"
                  />

                  <button
                    type="button"
                    className="qxdm-refresh-button"
                    onClick={handleBrowseAdb}
                  >
                    Browse
                  </button>
                </div>
              </label>
            </div>

            <div className="configuration-note throughput-note-stack">
              <div>
                <FiTerminal />
                <span>
                  adb shell cat /sys/module/qcom_dload_mode/parameters/download_mode
                </span>
              </div>

              <div>
                <FiTerminal />
                <span>
                  adb shell ./usr/sbin/QMI_VZW_ENABLE_RAMDUMP
                </span>
              </div>
            </div>

            <div className="qxdm-action-row">
              <button
                type="button"
                className="qxdm-start-button"
                onClick={handleCheckDownloadMode}
              >
                <FiTerminal />
                Check Download Mode
              </button>

              <button
                type="button"
                className="qxdm-start-button"
                onClick={handleEnableRamdump}
              >
                <FiServer />
                Enable RAM Dump
              </button>

              <button
                type="button"
                className="qxdm-start-button"
                onClick={handleOpenPcat}
              >
                <FiPlay />
                Open PCAT
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

            {downloadModeResult && (
              <div className="qxdm-manual-settings-banner">
                <strong>Download Mode Result</strong>
                <span>{downloadModeResult}</span>
              </div>
            )}
          </article>

          <article className="qxdm-monitor-card">
            <div className="panel-header">
              <div>
                <h3>RAM Dump Workflow</h3>
                <p>ADB preparation followed by PCAT GUI handling.</p>
              </div>

              <FiHardDrive />
            </div>

            <div className="wrapper-progress-list">
              {[
                ['1. Locate ADB', 'Use the platform-tools folder containing adb.exe.'],
                ['2. Check Download Mode', 'Run the qcom_dload_mode parameter command.'],
                ['3. Enable RAM Dump', 'Run QMI_VZW_ENABLE_RAMDUMP.'],
                ['4. Open PCAT', 'Continue the RAM dump workflow in the PCAT GUI.'],
                ['5. Store Artifacts', 'Save or copy dump artifacts into wrapper/pcat/.'],
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
      </main>
    </div>
  )
}

export default PCAT