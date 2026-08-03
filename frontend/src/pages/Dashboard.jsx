import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'
import DashboardCard from '../components/DashboardCard'
import '../App.css'

function Dashboard() {
  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar />

        <section className="dashboard-header">
          <div>
            <h2>Test Overview</h2>
            <p>Monitor devices, tests, logs, and network performance.</p>
          </div>

          <button className="start-test-button" type="button">
            Start New Test
          </button>
        </section>

        <section className="dashboard-cards">
          <DashboardCard
            title="Connected Devices"
            value="0"
            subtitle="No devices detected"
          />

          <DashboardCard
            title="Active Tests"
            value="0"
            subtitle="No test currently running"
          />

          <DashboardCard
            title="Current Throughput"
            value="0 Mbps"
            subtitle="Waiting for test data"
          />

          <DashboardCard
            title="QXDM Logs"
            value="0"
            subtitle="No logs captured"
          />
        </section>

        <section className="dashboard-grid">
          <article className="dashboard-panel throughput-panel">
            <div className="panel-header">
              <div>
                <h3>Throughput Monitor</h3>
                <p>Live download and upload performance</p>
              </div>

              <span className="status-badge idle">Idle</span>
            </div>

            <div className="empty-state">
              <p>No throughput data available.</p>
              <span>Start a test to begin monitoring.</span>
            </div>
          </article>

          <article className="dashboard-panel">
            <div className="panel-header">
              <div>
                <h3>Recent Activity</h3>
                <p>Latest TestHub events</p>
              </div>
            </div>

            <div className="empty-state">
              <p>No recent activity.</p>
              <span>New test events will appear here.</span>
            </div>
          </article>
        </section>
      </main>
    </div>
  )
}

export default Dashboard