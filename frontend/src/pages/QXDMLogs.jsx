import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";
import "../App.css";

function QXDMLogs() {
  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="QXDM Logs" />

        <section className="dashboard-panel">
          <h2>QXDM Logs</h2>
          <p>This page is under construction.</p>
        </section>
      </main>
    </div>
  );
}

export default QXDMLogs;