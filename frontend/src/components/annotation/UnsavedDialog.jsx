import { TriangleAlert } from 'lucide-react'

export function UnsavedDialog({ saving, onCancel, onDiscard, onSave }) {
  return <div className="modal-backdrop"><section className="class-dialog unsaved-dialog" role="alertdialog" aria-modal="true"><div className="class-dialog__header"><div><span className="eyebrow">UNSAVED CHANGES</span><h2>Save before leaving?</h2></div></div><div className="delete-warning"><TriangleAlert size={20} /><p>This image has annotation changes that have not been saved.</p></div><div className="dialog-actions"><button className="secondary-button" type="button" onClick={onCancel} disabled={saving}>Cancel</button><button className="secondary-button" type="button" onClick={onDiscard} disabled={saving}>Discard</button><button className="create-button" type="button" onClick={onSave} disabled={saving}>{saving ? 'Saving...' : 'Save & Continue'}</button></div></section></div>
}
