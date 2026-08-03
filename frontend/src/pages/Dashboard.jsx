import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'
import '../App.css'

function Dashboard() {
  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar />

        <section className="dashboard-section">
          <h2>WNC TestHub Dashboard</h2>
          <p>Frontend setup is working.</p>
        </section>
      </main>
    </div>
  )
}

export default Dashboard