import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";
import "../App.css";

function Analytics() {
  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="Analytics" />

        <section className="dashboard-panel">
          <h2>Analytics</h2>
          <p>Analytics and reports will appear here.</p>
        </section>
      </main>
    </div>
  );
}

export default Analytics;