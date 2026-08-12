import { useState } from 'react'
import {
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
import api from '../services/api'
import '../App.css'

function PCAT() {
  const [adbFolder, setAdbFolder] = useState('')
  const [pcatExecutable, setPcatExecutable] = useState('')
  const [downloadModeResult, setDownloadModeResult] = useState('')
  const [ramdumpResult, setRamdumpResult] = useState('')
  const [status, setStatus] = useState('idle')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busyAction, setBusyAction] = useState('')

  const statusLabel =
    status === 'checking'
      ? 'Checking Download Mode'
      : status === 'download-mode-checked'
        ? 'Download Mode Checked'
        : status === 'enabling'
          ? 'Enabling RAM Dump'
          : status === 'enabled'
            ? 'RAM Dump Enabled'
            : status === 'pcat-open'
              ? 'PCAT Open'
              : status === 'failed'
                ? 'Failed'
                : 'Idle'

  const handleBrowseAdb = async () => {
    setError('')
    setMessage('')

    try {
      const response = await api.get(
        '/pcat/browse-adb',
        {
          timeout: 0,
        }
      )

      if (response.data?.path) {
        setAdbFolder(response.data.path)
        setMessage(
          `ADB detected: ${response.data.adb_executable}`
        )
      }
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to select the platform-tools folder.'
      )
    }
  }

  const handleBrowsePcat = async () => {
    setError('')
    setMessage('')

    try {
      const response = await api.get(
        '/pcat/browse-executable',
        {
          timeout: 0,
        }
      )

      if (response.data?.path) {
        setPcatExecutable(response.data.path)
        setMessage('PCAT executable selected.')
      }
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to select the PCAT executable.'
      )
    }
  }

  const handleCheckDownloadMode = async () => {
    if (!adbFolder.trim()) {
      setError('Select the platform-tools folder first.')
      return
    }

    setError('')
    setMessage('')
    setStatus('checking')
    setBusyAction('check')

    try {
      const response = await api.post(
        '/pcat/check-download-mode',
        {
          adb_folder: adbFolder.trim(),
        },
        {
          timeout: 45000,
        }
      )

      const output =
        response.data?.stdout ||
        response.data?.message ||
        'Command completed without output.'

      setDownloadModeResult(output)
      setStatus('download-mode-checked')
      setMessage(response.data?.message ?? '')
    } catch (requestError) {
      setStatus('failed')
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to check download mode.'
      )
    } finally {
      setBusyAction('')
    }
  }

  const handleEnableRamdump = async () => {
    if (!adbFolder.trim()) {
      setError('Select the platform-tools folder first.')
      return
    }

    setError('')
    setMessage('')
    setStatus('enabling')
    setBusyAction('enable')

    try {
      const response = await api.post(
        '/pcat/enable-ramdump',
        {
          adb_folder: adbFolder.trim(),
        },
        {
          timeout: 45000,
        }
      )

      const output =
        response.data?.stdout ||
        response.data?.message ||
        'RAM dump command completed without output.'

      setRamdumpResult(output)
      setStatus('enabled')
      setMessage(response.data?.message ?? '')
    } catch (requestError) {
      setStatus('failed')
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to enable RAM dump.'
      )
    } finally {
      setBusyAction('')
    }
  }

  const handleOpenPcat = async () => {
    setError('')
    setMessage('')
    setBusyAction('pcat')

    try {
      const response = await api.post(
        '/pcat/open',
        {
          pcat_executable:
            pcatExecutable.trim() || null,
        },
        {
          timeout: 0,
        }
      )

      if (response.data?.pcat_executable) {
        setPcatExecutable(
          response.data.pcat_executable
        )
      }

      if (!response.data?.cancelled) {
        setStatus('pcat-open')
      }

      setMessage(response.data?.message ?? '')
    } catch (requestError) {
      setStatus('failed')
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to open PCAT.'
      )
    } finally {
      setBusyAction('')
    }
  }

  const handleRefresh = async () => {
    setError('')

    try {
      const response = await api.get('/pcat/status')

      if (response.data?.adb_folder) {
        setAdbFolder(response.data.adb_folder)
      }

      if (response.data?.pcat_executable) {
        setPcatExecutable(
          response.data.pcat_executable
        )
      }

      if (response.data?.download_mode_result) {
        setDownloadModeResult(
          response.data.download_mode_result
        )
      }

      if (response.data?.ramdump_result) {
        setRamdumpResult(
          response.data.ramdump_result
        )
      }

      setMessage(response.data?.message ?? '')
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          requestError.message ||
          'Unable to refresh PCAT status.'
      )
    }
  }

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="PCAT" />

        <section className="page-heading">
          <div>
            <h2>PCAT RAM Dump</h2>
            <p>
              Prepare RAM dump mode using ADB, then open PCAT and
              continue the CrashDump workflow.
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
              <FiPlay />
            </div>
            <div>
              <p>PCAT Application</p>
              <h3>
                {pcatExecutable ? 'Configured' : 'Not Configured'}
              </h3>
              <span>
                {pcatExecutable || 'Select PCAT executable'}
              </span>
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
                  TestHub runs the two required ADB commands directly.
                  PCAT remains completely separate from the Test Wrapper.
                </p>
              </div>
            </div>

            <div className="qxdm-form-grid">
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
                    disabled={Boolean(busyAction)}
                  >
                    Browse
                  </button>
                </div>
              </label>

              <label className="form-field qxdm-folder-field">
                <span>PCAT Executable</span>

                <div className="qxdm-folder-input">
                  <FiPlay />

                  <input
                    type="text"
                    value={pcatExecutable}
                    onChange={(event) =>
                      setPcatExecutable(event.target.value)
                    }
                    placeholder="Select PCAT .exe"
                  />

                  <button
                    type="button"
                    className="qxdm-refresh-button"
                    onClick={handleBrowsePcat}
                    disabled={Boolean(busyAction)}
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

            {error && (
              <div className="api-error-message">
                <strong>PCAT error:</strong> {error}
              </div>
            )}

            {message && (
              <div className="qxdm-manual-settings-banner">
                <strong>PCAT Status</strong>
                <span>{message}</span>
              </div>
            )}

            <div className="qxdm-action-row">
              <button
                type="button"
                className="qxdm-start-button"
                onClick={handleCheckDownloadMode}
                disabled={Boolean(busyAction)}
              >
                <FiTerminal />
                {busyAction === 'check'
                  ? 'Checking...'
                  : 'Check Download Mode'}
              </button>

              <button
                type="button"
                className="qxdm-start-button"
                onClick={handleEnableRamdump}
                disabled={Boolean(busyAction)}
              >
                <FiServer />
                {busyAction === 'enable'
                  ? 'Enabling...'
                  : 'Enable RAM Dump'}
              </button>

              <button
                type="button"
                className="qxdm-start-button"
                onClick={handleOpenPcat}
                disabled={Boolean(busyAction)}
              >
                <FiPlay />
                {busyAction === 'pcat'
                  ? 'Opening...'
                  : 'Open PCAT'}
              </button>

              <button
                type="button"
                className="qxdm-refresh-button"
                onClick={handleRefresh}
                disabled={Boolean(busyAction)}
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

            {ramdumpResult && (
              <div className="qxdm-manual-settings-banner">
                <strong>Enable RAM Dump Result</strong>
                <span>{ramdumpResult}</span>
              </div>
            )}
          </article>

          <article className="qxdm-monitor-card">
            <div className="panel-header">
              <div>
                <h3>RAM Dump Workflow</h3>
                <p>
                  ADB preparation followed by PCAT GUI handling.
                </p>
              </div>

              <FiHardDrive />
            </div>

            <div className="wrapper-progress-list">
              {[
                [
                  '1. Locate ADB',
                  'Select the platform-tools folder containing adb.exe.',
                ],
                [
                  '2. Check Download Mode',
                  'TestHub runs the qcom_dload_mode parameter command.',
                ],
                [
                  '3. Enable RAM Dump',
                  'TestHub runs QMI_VZW_ENABLE_RAMDUMP.',
                ],
                [
                  '4. Open PCAT',
                  'Launch PCAT and continue the RAM dump workflow.',
                ],
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