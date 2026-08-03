function Topbar({ title = "Dashboard" }) {
  return (
    <header className="topbar">
      <h1>{title}</h1>
      <p className="status-online">System Status: Online</p>
    </header>
  );
}

export default Topbar;