import { NavLink } from 'react-router-dom'
import {
  FiHome,
  FiCpu,
  FiFileText,
  FiActivity,
  FiBarChart2,
  FiLayers,
  FiSettings,
} from 'react-icons/fi'
import logo from '../assets/wnc-logo.png'

function Sidebar() {
  const getLinkClass = ({ isActive }) =>
    `sidebar-link ${isActive ? 'active' : ''}`

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <img
          src={logo}
          alt="WNC"
          className="sidebar-logo"
        />

        <div>
          <h2 className="sidebar-title">WNC</h2>
          <p className="sidebar-subtitle">TestHub</p>
        </div>
      </div>

      <nav className="sidebar-nav">
        <NavLink to="/" end className={getLinkClass}>
          <FiHome className="sidebar-icon" />
          <span>Dashboard</span>
        </NavLink>

        <NavLink to="/devices" className={getLinkClass}>
          <FiCpu className="sidebar-icon" />
          <span>Devices</span>
        </NavLink>

        <NavLink to="/qxdm-logs" className={getLinkClass}>
          <FiFileText className="sidebar-icon" />
          <span>QXDM Logs</span>
        </NavLink>

        <NavLink to="/throughput" className={getLinkClass}>
          <FiActivity className="sidebar-icon" />
          <span>Throughput</span>
        </NavLink>

        <NavLink to="/analytics" className={getLinkClass}>
          <FiBarChart2 className="sidebar-icon" />
          <span>Analytics</span>
        </NavLink>

        <NavLink to="/test-wrapper" className={getLinkClass}>
          <FiLayers className="sidebar-icon" />
          <span>Test Wrapper</span>
        </NavLink>

        <NavLink to="/settings" className={getLinkClass}>
          <FiSettings className="sidebar-icon" />
          <span>Settings</span>
        </NavLink>
      </nav>
    </aside>
  )
}

export default Sidebar