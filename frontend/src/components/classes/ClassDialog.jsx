import { useEffect, useState } from 'react'
import { Palette, TriangleAlert, X } from 'lucide-react'

const COLOR_PRESETS = ['#FF5D68', '#FF9F43', '#F6C445', '#50D69A', '#3ED6D0', '#62A6FF', '#8B7CFF', '#D36BFF']

export function ClassDialog({ record, saving, error, onClose, onSubmit }) {
  const [name, setName] = useState(record?.name || '')
  const [color, setColor] = useState(record?.color || COLOR_PRESETS[0])
  const [validation, setValidation] = useState('')

  useEffect(() => {
    const closeOnEscape = (event) => { if (event.key === 'Escape' && !saving) onClose() }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose, saving])

  const submit = async (event) => {
    event.preventDefault()
    if (!name.trim()) {
      setValidation('Class name is required.')
      return
    }
    const succeeded = await onSubmit({ name: name.trim(), color })
    if (succeeded) onClose()
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && !saving && onClose()}>
      <section className="class-dialog" role="dialog" aria-modal="true" aria-labelledby="class-dialog-title">
        <div className="class-dialog__header">
          <div><span className="eyebrow">CLASS DEFINITION</span><h2 id="class-dialog-title">{record ? 'Edit class' : 'Add class'}</h2></div>
          <button className="icon-button" type="button" aria-label="Close" onClick={onClose} disabled={saving}><X size={18} /></button>
        </div>
        <form onSubmit={submit}>
          <label className="form-field">
            <span>Class name</span>
            <input autoFocus maxLength="100" value={name} onChange={(event) => { setName(event.target.value); setValidation('') }} placeholder="e.g. Motorcycle" />
          </label>
          {validation && <span className="field-error">{validation}</span>}
          {error && <div className="feedback feedback--error dialog-feedback"><TriangleAlert size={16} /><span>{error}</span></div>}
          <fieldset className="color-field">
            <legend>Display color</legend>
            <div className="color-picker-row">
              <label className="native-color" style={{ backgroundColor: color }} title="Choose a custom color"><input type="color" value={color} onChange={(event) => setColor(event.target.value.toUpperCase())} /><Palette size={17} /></label>
              <code>{color.toUpperCase()}</code>
            </div>
            <div className="color-presets" aria-label="Color presets">
              {COLOR_PRESETS.map((preset) => <button className={color.toUpperCase() === preset ? 'active' : ''} style={{ backgroundColor: preset }} type="button" key={preset} aria-label={`Use ${preset}`} onClick={() => setColor(preset)} />)}
            </div>
          </fieldset>
          <div className="dialog-actions">
            <button className="secondary-button" type="button" onClick={onClose} disabled={saving}>Cancel</button>
            <button className="create-button" type="submit" disabled={saving}>{saving ? 'Saving...' : record ? 'Save changes' : 'Create class'}</button>
          </div>
        </form>
      </section>
    </div>
  )
}
