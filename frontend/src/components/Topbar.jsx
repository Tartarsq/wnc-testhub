import { useEffect, useState } from 'react'
import api from '../services/api'

function Topbar({ title = 'Dashboard' }) {
  const [systemStatus, setSystemStatus] = useState('checking')

  useEffect(() => {
    const checkBackendHealth = async () => {
      try {
        const response = await api.get('/health')

        setSystemStatus(
          response.data?.status === 'online'
            ? 'online'
            : 'offline'
        )
      } catch (error) {
        console.error('Health check failed:', error)
        setSystemStatus('offline')
      }
    }

    checkBackendHealth()

    const interval = window.setInterval(
      checkBackendHealth,
      10000
    )

    return () => {
      window.clearInterval(interval)
    }
  }, [])

  const statusLabel =
    systemStatus === 'checking'
      ? 'Checking'
      : systemStatus === 'online'
        ? 'Online'
        : 'Offline'

  return (
    <header className="topbar">
      <h1>{title}</h1>

      <p className={`system-status ${systemStatus}`}>
        <span className="status-dot" />
        System Status: {statusLabel}
      </p>
    </header>
  )
}

export default Topbar