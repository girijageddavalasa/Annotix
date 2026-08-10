import { useState } from 'react'
import { TriangleAlert, X } from 'lucide-react'

export function ProjectDialog({ mode, project, busy, error, onClose, onSubmit }) {
  const [name, setName] = useState(project?.name || '')
  const [validation, setValidation] = useState('')
  const deleting = mode === 'delete'
  const submit = async (event) => {
    event.preventDefault()
    if (!deleting && !name.trim()) { setValidation('Project name is required.'); return }
    if (await onSubmit(deleting ? undefined : name.trim())) onClose()
  }
  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}><section className={`class-dialog project-dialog${deleting ? ' project-dialog--delete' : ''}`} role="dialog" aria-modal="true"><div className="class-dialog__header"><div><span className="eyebrow">{deleting ? 'PERMANENT ACTION' : 'PROJECT'}</span><h2>{mode === 'create' ? 'Create new project' : deleting ? `Delete “${project.name}”?` : 'Rename project'}</h2></div><button className="icon-button" type="button" onClick={onClose} disabled={busy} aria-label="Close"><X size={18} /></button></div><form onSubmit={submit}>{deleting ? <><div className="project-delete-warning"><TriangleAlert size={22} /><div><strong>This action cannot be undone.</strong><p>The local project workspace and all its images, annotations, classes, generated files, models, and logs will be permanently removed.</p></div></div><dl className="project-delete-stats"><div><dt>Images</dt><dd>{project.stats.images}</dd></div><div><dt>Annotations</dt><dd>{project.stats.annotations}</dd></div><div><dt>Classes</dt><dd>{project.stats.classes}</dd></div></dl></> : <label className="form-field"><span>Project name</span><input autoFocus maxLength="120" value={name} onChange={(event) => { setName(event.target.value); setValidation('') }} placeholder="e.g. Vehicle Detection" /></label>}{validation && <span className="field-error">{validation}</span>}{error && <div className="feedback feedback--error dialog-feedback"><TriangleAlert size={16} />{error}</div>}<div className="dialog-actions"><button className="secondary-button" type="button" onClick={onClose} disabled={busy}>Cancel</button><button className={deleting ? 'delete-button' : 'create-button'} type="submit" disabled={busy}>{busy ? 'Working...' : deleting ? 'Delete project' : mode === 'create' ? 'Create project' : 'Save name'}</button></div></form></section></div>
}
