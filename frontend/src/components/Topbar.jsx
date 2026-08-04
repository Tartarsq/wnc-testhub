import { useEffect, useState } from 'react'
import api from '../services/api'

function Topbar({ title = 'Dashboard' }) {
  const [systemStatus, setSystemStatus] = useState('checking')

  useEffect(() => {
    let isMounted = true

    const checkBackendHealth = async () => {
      try {
        const response = await api.get('/health')

        if (
          isMounted &&
          response.data?.status === 'online'
        ) {
          setSystemStatus('online')
        } else if (isMounted) {
          setSystemStatus('offline')
        }
      } catch {
        if (isMounted) {
          setSystemStatus('offline')
        }
      }
    }

    checkBackendHealth()

    const healthInterval = window.setInterval(
      checkBackendHealth,
      10000
    )

    return () => {
      isMounted = false
      window.clearInterval(healthInterval)
    }
  }, [])

  const statusLabel = {
    checking: 'Checking',
    online: 'Online',
    offline: 'Offline',
  }[systemStatus]

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