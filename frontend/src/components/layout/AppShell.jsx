import { Header } from './Header'
import { Sidebar } from './Sidebar'

export function AppShell({ children, currentPage, onNavigate, stats, projectState, projectBusy, projectActions, projectLocked }) {
  return (
    <div className="app-shell">
      <Header projectState={projectState} busy={projectBusy} projectLocked={projectLocked} {...projectActions} />
      <Sidebar currentPage={currentPage} onNavigate={onNavigate} stats={stats} />
      <main className={`main-content${currentPage === 'Annotation' ? ' main-content--annotation' : ''}`}>{children}</main>
    </div>
  )
}
