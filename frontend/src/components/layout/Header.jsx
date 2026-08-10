import { useState } from 'react'
import { Check, ChevronDown, CircleHelp, Edit3, Plus, Settings, Trash2 } from 'lucide-react'

import { Logo } from '../branding/Logo'
import { ProjectDialog } from '../projects/ProjectDialog'

export function Header({ projectState, busy, projectLocked, onActivate, onCreate, onRename, onDelete }) {
  const [open, setOpen] = useState(false)
  const [dialog, setDialog] = useState(null)
  const { projects, currentProject, loading, error, clearError } = projectState
  const showDialog = (mode, project = currentProject) => { clearError(); setOpen(false); setDialog({ mode, project }) }
  const closeDialog = () => { if (!busy) { clearError(); setDialog(null) } }
  const submitDialog = (name) => dialog.mode === 'create' ? onCreate(name) : dialog.mode === 'rename' ? onRename(dialog.project.id, name) : onDelete(dialog.project.id)

  return <>
    <header className="topbar">
      <Logo />
      <div className="topbar__project project-menu-wrap">
        <span className="eyebrow">CURRENT PROJECT</span>
        <button className="project-switcher" type="button" onClick={() => setOpen((value) => !value)} disabled={loading || busy}>{currentProject?.name || 'Loading project'} <ChevronDown size={15} /></button>
        {open && <div className="project-popover">
          <div className="project-popover__title"><span>PROJECTS</span><strong>{projects.length}</strong></div>
          <div className="project-list">{projects.map((project) => <button className={project.id === currentProject?.id ? 'active' : ''} type="button" key={project.id} onClick={async () => { if (project.id === currentProject?.id || await onActivate(project.id)) setOpen(false) }}><span>{project.id === currentProject?.id ? <Check size={14} /> : null}</span><div><strong>{project.name}</strong><small>{project.stats.images} images · {project.stats.annotations} objects</small></div></button>)}</div>
          <div className="project-popover__actions"><button type="button" onClick={() => showDialog('create', null)}><Plus size={15} /> Create new project</button>{currentProject && <><button type="button" onClick={() => showDialog('rename')}><Edit3 size={14} /> Rename current</button><button className="danger" type="button" disabled={projectLocked} onClick={() => showDialog('delete')}><Trash2 size={14} /> Delete current</button></>}</div>
        </div>}
      </div>
      <div className="topbar__actions"><span className="local-badge"><span className="status-dot" /> Local workspace</span><button className="icon-button" type="button" aria-label="Help"><CircleHelp size={19} /></button><button className="icon-button" type="button" aria-label="Settings"><Settings size={19} /></button></div>
    </header>
    {dialog && <ProjectDialog mode={dialog.mode} project={dialog.project} busy={busy} error={error} onClose={closeDialog} onSubmit={submitDialog} />}
  </>
}
