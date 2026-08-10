export function StatCard({ icon: Icon, label, value, detail, accent }) {
  return (
    <article className="stat-card">
      <div className={`stat-card__icon stat-card__icon--${accent}`}><Icon size={20} /></div>
      <div>
        <span className="stat-card__label">{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </article>
  )
}

