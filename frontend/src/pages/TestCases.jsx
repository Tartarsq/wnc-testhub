import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";
import "../App.css";

function TestCases() {
  return (
    <div className="dashboard-layout">
      <Sidebar />

      <main className="main-content">
        <Topbar title="Test Cases" />

        <section className="dashboard-panel">
          <h2>Test Cases</h2>
          <p>Manage test cases from this page.</p>
        </section>
      </main>
    </div>
  );
}

export default TestCases;