import { useEffect, useState } from 'react'
import {
  FiActivity,
  FiDatabase,
  FiRefreshCw,
  FiSave,
  FiServer,
  FiSettings,
} from 'react-icons/fi'
import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'
import '../App.css'

const DEFAULT_SETTINGS = {
  titanIp: '192.168.100.1',
  numberOfRuns: 5,
  delaySeconds: 10,
  timeoutSeconds: 180,
  deviceRefreshSeconds: 10,
  qxdmExecutable: '',
  qxdmMaskPath: '',
  defaultLogFolder: '',
}

function Settings() {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [savedMessage, setSavedMessage] = useState('')

  useEffect(() => {
    const storedSettings = window.localStorage.getItem(
      'wncTestHubSettings'
    )

    if (!storedSettings) {
      return
    }

    try {
      setSettings({
        ...DEFAULT_SETTINGS,
        ...JSON.parse(storedSettings),
      })
    } catch {
      window.localStorage.removeItem('wncTestHubSettings')
    }
  }, [])

  const updateSetting = (field, value) => {
    setSettings((current) => ({
      ...current,
      [field]: value,
    }))
    setSavedMessage('')
  }

  const handleSave = () => {
    const normalizedSettings = {
      ...settings,
      titanIp: settings.titanIp.trim(),
      numberOfRuns: Number(settings.numberOfRuns),
      delaySeconds: Number(settings.delaySeconds),
      timeoutSeconds: Number(settings.timeoutSeconds),
      deviceRefreshSeconds: Number(
        settings.deviceRefreshSeconds
      ),
      qxdmExecutable: settings.qxdmExecutable.trim(),
      qxdmMaskPath: settings.qxdmMaskPath.trim(),
      defaultLogFolder: settings.defaultLogFolder.trim(),
    }

    window.localStorage.setItem(
      'wncTestHubSettings',
      JSON.stringify(normalizedSettings)
    )

    setSettings(normalizedSettings)
    setSavedMessage('Settings saved successfully.')
  }

  const handleRestoreDefaults = () => {
    setSettings(DEFAULT_SETTINGS)
    window.localStorage.setItem(
      'wncTestHubSettings',
      JSON.stringify(DEFAULT_SETTINGS)
    )
    setSavedMessage('Default settings restored.')
  }

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="Settings" />

        <section className="page-heading settings-page-heading">
          <div>
            <h2>TestHub Settings</h2>
            <p>
              Manage shared defaults for devices, throughput,
              and future QXDM integrations.
            </p>
          </div>

          <span className="settings-version-badge">
            Version 1.0.0
          </span>
        </section>

        <section className="settings-grid">
          <article className="settings-card">
            <div className="settings-card-header">
              <span className="settings-card-icon throughput">
                <FiActivity />
              </span>
              <div>
                <h3>Throughput Defaults</h3>
                <p>
                  Values automatically loaded on the Throughput page.
                </p>
              </div>
            </div>

            <div className="settings-form-grid">
              <label className="form-field settings-full-field">
                <span>Default Titan IP</span>
                <input
                  type="text"
                  value={settings.titanIp}
                  onChange={(event) =>
                    updateSetting('titanIp', event.target.value)
                  }
                />
              </label>

              <label className="form-field">
                <span>Default Runs</span>
                <input
                  type="number"
                  min="1"
                  max="15"
                  value={settings.numberOfRuns}
                  onChange={(event) =>
                    updateSetting(
                      'numberOfRuns',
                      Number(event.target.value)
                    )
                  }
                />
              </label>

              <label className="form-field">
                <span>Delay Between Runs</span>
                <div className="input-with-unit">
                  <input
                    type="number"
                    min="0"
                    max="3600"
                    value={settings.delaySeconds}
                    onChange={(event) =>
                      updateSetting(
                        'delaySeconds',
                        Number(event.target.value)
                      )
                    }
                  />
                  <span>sec</span>
                </div>
              </label>

              <label className="form-field settings-full-field">
                <span>Default Timeout</span>
                <div className="input-with-unit">
                  <input
                    type="number"
                    min="1"
                    max="1800"
                    value={settings.timeoutSeconds}
                    onChange={(event) =>
                      updateSetting(
                        'timeoutSeconds',
                        Number(event.target.value)
                      )
                    }
                  />
                  <span>sec</span>
                </div>
              </label>
            </div>
          </article>

          <article className="settings-card">
            <div className="settings-card-header">
              <span className="settings-card-icon device">
                <FiServer />
              </span>
              <div>
                <h3>Device Settings</h3>
                <p>
                  Configure how often TestHub refreshes device data.
                </p>
              </div>
            </div>

            <div className="settings-form-grid">
              <label className="form-field settings-full-field">
                <span>Device Refresh Interval</span>
                <div className="input-with-unit">
                  <input
                    type="number"
                    min="5"
                    max="300"
                    value={settings.deviceRefreshSeconds}
                    onChange={(event) =>
                      updateSetting(
                        'deviceRefreshSeconds',
                        Number(event.target.value)
                      )
                    }
                  />
                  <span>sec</span>
                </div>
              </label>
            </div>

            <div className="settings-info-box">
              <FiRefreshCw />
              <span>
                This preference is saved now and can be connected
                to the Devices and Dashboard refresh timers later.
              </span>
            </div>
          </article>

          <article className="settings-card settings-wide-card">
            <div className="settings-card-header">
              <span className="settings-card-icon qxdm">
                <FiDatabase />
              </span>
              <div>
                <h3>QXDM Defaults</h3>
                <p>
                  Save common paths for future QXDM configuration.
                </p>
              </div>
            </div>

            <div className="settings-form-grid">
              <label className="form-field settings-full-field">
                <span>QXDM Executable</span>
                <input
                  type="text"
                  value={settings.qxdmExecutable}
                  onChange={(event) =>
                    updateSetting(
                      'qxdmExecutable',
                      event.target.value
                    )
                  }
                  placeholder="C:\Program Files\Qualcomm\QXDM\QXDM.exe"
                />
              </label>

              <label className="form-field settings-full-field">
                <span>Default DMC Configuration</span>
                <input
                  type="text"
                  value={settings.qxdmMaskPath}
                  onChange={(event) =>
                    updateSetting(
                      'qxdmMaskPath',
                      event.target.value
                    )
                  }
                  placeholder="C:\TestHub\config\Default.dmc"
                />
              </label>

              <label className="form-field settings-full-field">
                <span>Default Log Folder</span>
                <input
                  type="text"
                  value={settings.defaultLogFolder}
                  onChange={(event) =>
                    updateSetting(
                      'defaultLogFolder',
                      event.target.value
                    )
                  }
                  placeholder="C:\TestHub\logs"
                />
              </label>
            </div>

            <div className="settings-info-box warning">
              <FiSettings />
              <span>
                These QXDM values are stored for future integration.
                The current working QXDM automation is unchanged.
              </span>
            </div>
          </article>
        </section>

        <section className="settings-action-bar">
          <div>
            <strong>Local Settings</strong>
            <span>
              Preferences are stored in this browser using localStorage.
            </span>
          </div>

          <div className="settings-action-buttons">
            <button
              type="button"
              className="settings-reset-button"
              onClick={handleRestoreDefaults}
            >
              <FiRefreshCw />
              Restore Defaults
            </button>

            <button
              type="button"
              className="settings-save-button"
              onClick={handleSave}
            >
              <FiSave />
              Save Settings
            </button>
          </div>
        </section>

        {savedMessage && (
          <div className="settings-saved-message">
            {savedMessage}
          </div>
        )}
      </main>
    </div>
  )
}

export default Settings