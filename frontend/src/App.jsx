import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Devices from './pages/devices'
import QXDMLogs from './pages/QXDMLogs'
import Throughput from './pages/Throughput'
import Analytics from './pages/Analytics'
import TestResultDetails from './pages/TestResultDetails'
import Settings from './pages/Settings'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/devices" element={<Devices />} />
        <Route path="/qxdm-logs" element={<QXDMLogs />} />
        <Route path="/throughput" element={<Throughput />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route
          path="/analytics/results/:resultIndex"
          element={<TestResultDetails />}
        />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App