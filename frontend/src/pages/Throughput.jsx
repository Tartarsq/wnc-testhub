import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";
import "../App.css";

function Throughput() {
  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="Throughput" />

        <section className="dashboard-panel">
          <h2>Throughput</h2>
          <p>Throughput graphs will appear here.</p>
        </section>
      </main>
    </div>
  );
}

export default Throughput;