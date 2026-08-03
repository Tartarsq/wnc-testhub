function Sidebar() {
  return (
    <aside className="sidebar">
      <h2 className="sidebar-title">WNC TestHub</h2>

      <nav className="sidebar-nav">
        <div className="sidebar-link active">Dashboard</div>
        <div className="sidebar-link">Devices</div>
        <div className="sidebar-link">QXDM Logs</div>
        <div className="sidebar-link">Throughput</div>
        <div className="sidebar-link">Test Cases</div>
        <div className="sidebar-link">Analytics</div>
        <div className="sidebar-link">Settings</div>
      </nav>
    </aside>
  )
}

export default Sidebar