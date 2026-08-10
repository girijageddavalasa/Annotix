import { TriangleAlert, X } from 'lucide-react'

export function DeleteClassDialog({ record, saving, error, onClose, onConfirm }) {
  const inUse = record.usage_count > 0
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && !saving && onClose()}>
      <section className="class-dialog delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-dialog-title">
        <div className="class-dialog__header">
          <div><span className="eyebrow">DELETE CLASS</span><h2 id="delete-dialog-title">Delete “{record.name}”?</h2></div>
          <button className="icon-button" type="button" aria-label="Close" onClick={onClose} disabled={saving}><X size={18} /></button>
        </div>
        <div className={`delete-warning${inUse ? ' delete-warning--blocked' : ''}`}>
          <TriangleAlert size={21} />
          <p>{inUse
            ? `This class is used by ${record.usage_count} annotations. It cannot be deleted until those annotations are reassigned or removed.`
            : 'This removes the class from this project. Its ID will remain retired and will not be reused.'}</p>
        </div>
        {error && <div className="feedback feedback--error dialog-feedback"><TriangleAlert size={16} /><span>{error}</span></div>}
        <div className="dialog-actions">
          <button className="secondary-button" type="button" onClick={onClose} disabled={saving}>{inUse ? 'Close' : 'Cancel'}</button>
          {!inUse && <button className="delete-button" type="button" onClick={onConfirm} disabled={saving}>{saving ? 'Deleting...' : 'Delete class'}</button>}
        </div>
      </section>
    </div>
  )
}
