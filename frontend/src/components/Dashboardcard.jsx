function DashboardCard({ title, value, subtitle }) {
  return (
    <article className="dashboard-card">
      <p className="card-title">{title}</p>
      <h3 className="card-value">{value}</h3>
      <p className="card-subtitle">{subtitle}</p>
    </article>
  )
}

export default DashboardCard