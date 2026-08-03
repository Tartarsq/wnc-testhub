import { NavLink } from 'react-router-dom'

function Sidebar() {
  const getLinkClass = ({ isActive }) =>
    `sidebar-link ${isActive ? 'active' : ''}`

  return (
    <aside className="sidebar">
      <h2 className="sidebar-title">WNC TestHub</h2>

      <nav className="sidebar-nav">
        <NavLink to="/" end className={getLinkClass}>
          Dashboard
        </NavLink>

        <NavLink to="/devices" className={getLinkClass}>
          Devices
        </NavLink>

        <NavLink to="/qxdm-logs" className={getLinkClass}>
          QXDM Logs
        </NavLink>

        <NavLink to="/throughput" className={getLinkClass}>
          Throughput
        </NavLink>

        <NavLink to="/test-cases" className={getLinkClass}>
          Test Cases
        </NavLink>

        <NavLink to="/analytics" className={getLinkClass}>
          Analytics
        </NavLink>

        <NavLink to="/settings" className={getLinkClass}>
          Settings
        </NavLink>
      </nav>
    </aside>
  )
}

export default Sidebar