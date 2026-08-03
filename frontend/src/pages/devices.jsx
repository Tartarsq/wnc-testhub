import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';
import '../App.css';

function Devices() {
  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="Devices" />

        <section className="dashboard-panel">
          <h2>Connected Devices</h2>
          <p>Device information will appear here.</p>
        </section>
      </main>
    </div>
  );
}

export default Devices;