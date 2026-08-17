import {
  Archive,
  Boxes,
  ClipboardCheck,
  Database,
  Download,
  GraduationCap,
  LayoutDashboard,
  ShieldCheck,
} from 'lucide-react'

const navigation = [
  { label: 'Overview', icon: LayoutDashboard, enabled: true },
  { label: 'Dataset', icon: Database, enabled: true },
  { label: 'Annotation', icon: Boxes, enabled: true },
  { label: 'Classes', icon: Archive, enabled: true },
  { label: 'Training', icon: GraduationCap, enabled: true },
  { label: 'Review', icon: ClipboardCheck, enabled: true },
  { label: 'Export', icon: Download, enabled: true },
  { label: 'Validation', icon: ShieldCheck, enabled: true },
]

export function Sidebar({ currentPage, onNavigate, stats }) {
  return (
    <aside className="sidebar">
      <nav className="sidebar__nav" aria-label="Primary navigation">
        <span className="sidebar__label">WORKSPACE</span>
        {navigation.map(({ label, icon: Icon, enabled }) => (
          <button
            className={`nav-item${currentPage === label ? ' nav-item--active' : ''}`}
            type="button"
            key={label}
            onClick={() => enabled && onNavigate(label)}
            disabled={!enabled}
          >
            <Icon size={18} />
            <span>{label}</span>
            {!enabled && <span className="nav-item__soon">SOON</span>}
          </button>
        ))}
      </nav>
      <div className="project-status">
        <div className="project-status__heading">
          <span>PROJECT STATUS</span>
          <span className="status-dot" />
        </div>
        <dl>
          <div><dt>Images</dt><dd>{stats.total_images}</dd></div>
          <div><dt>Annotated</dt><dd>{stats.annotated_images}</dd></div>
          <div><dt>Classes</dt><dd>{stats.classes}</dd></div>
        </dl>
        <div className="progress-track"><span style={{ width: stats.total_images ? `${(stats.annotated_images / stats.total_images) * 100}%` : '3%' }} /></div>
        <small>{stats.total_images ? `${stats.unannotated_images} images ready to annotate` : 'Ready for a local dataset'}</small>
      </div>
    </aside>
  )
}
