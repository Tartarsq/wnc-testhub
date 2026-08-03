import { NavLink } from "react-router-dom";
import logo from "../assets/wnc-logo.png";

function Sidebar() {
  const getLinkClass = ({ isActive }) =>
    `sidebar-link ${isActive ? "active" : ""}`;

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <img src={logo} alt="WNC Logo" className="sidebar-logo" />

        <div>
          <h2 className="sidebar-title">WNC</h2>
          <p className="sidebar-subtitle">TestHub</p>
        </div>
      </div>

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
  );
}

export default Sidebar;