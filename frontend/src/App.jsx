import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Devices from './pages/Devices'
import QXDMLogs from './pages/QXDMLogs'
import Throughput from './pages/Throughput'
import TestCases from './pages/TestCases'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/devices" element={<Devices />} />
        <Route path="/qxdm-logs" element={<QXDMLogs />} />
        <Route path="/throughput" element={<Throughput />} />
        <Route path="/test-cases" element={<TestCases />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App