import { TriangleAlert } from 'lucide-react'

export function ProjectUnsavedDialog({ busy, onCancel, onDiscard, onSave }) {
  return <div className="modal-backdrop"><section className="class-dialog unsaved-dialog" role="alertdialog" aria-modal="true"><div className="class-dialog__header"><div><span className="eyebrow">UNSAVED ANNOTATIONS</span><h2>Save before changing projects?</h2></div></div><div className="delete-warning"><TriangleAlert size={20} /><p>You have unsaved annotation changes in the current project.</p></div><div className="dialog-actions"><button className="secondary-button" type="button" onClick={onCancel} disabled={busy}>Cancel</button><button className="secondary-button" type="button" onClick={onDiscard} disabled={busy}>Discard & Switch</button><button className="create-button" type="button" onClick={onSave} disabled={busy}>{busy ? 'Saving...' : 'Save & Switch'}</button></div></section></div>
}
