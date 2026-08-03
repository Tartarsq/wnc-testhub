import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";
import "../App.css";

function Settings() {
  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="Settings" />

        <section className="dashboard-panel">
          <h2>Settings</h2>
          <p>Configure TestHub settings here.</p>
        </section>
      </main>
    </div>
  );
}

export default Settings;