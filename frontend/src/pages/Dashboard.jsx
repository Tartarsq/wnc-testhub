import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'

function Dashboard() {
  return (
    <div>
      <Sidebar />

      <main>
        <Topbar />

        <section>
          <h2>WNC TestHub Dashboard</h2>
          <p>Frontend setup is working.</p>
        </section>
      </main>
    </div>
  )
}

export default Dashboard