import { useMemo, useState } from 'react'
import { Box, Boxes, CheckCircle2, Edit3, Layers3, Plus, Tag, Trash2, TriangleAlert } from 'lucide-react'

import { ClassDialog } from '../components/classes/ClassDialog'
import { DeleteClassDialog } from '../components/classes/DeleteClassDialog'
import { StatCard } from '../components/ui/StatCard'

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric' }).format(new Date(value))
}

export function Classes({ classState, locked = false }) {
  const { classes, loading, saving, error, success, clearFeedback, add, edit, remove } = classState
  const [editing, setEditing] = useState(undefined)
  const [deleting, setDeleting] = useState(null)
  const totalObjects = useMemo(() => classes.reduce((total, record) => total + record.usage_count, 0), [classes])
  const mostUsed = useMemo(() => {
    if (!totalObjects) return null
    return classes.reduce((current, record) => record.usage_count > current.usage_count ? record : current)
  }, [classes, totalObjects])

  const openCreate = () => { clearFeedback(); setEditing(null) }
  const openEdit = (record) => { clearFeedback(); setEditing(record) }

  return (
    <div className="dashboard classes-page">
      <div className="page-heading classes-heading">
        <div><span className="eyebrow">PROJECT LABELS</span><h1>Classes</h1><p>Define the objects you want to annotate in this dataset.</p></div>
        <button className="create-button" type="button" disabled={locked} onClick={openCreate}><Plus size={17} /> Add class</button>
      </div>

      <section className="stats-grid" aria-label="Class statistics">
        <StatCard icon={Layers3} label="TOTAL CLASSES" value={classes.length} detail="labels configured" accent="blue" />
        <StatCard icon={Boxes} label="ANNOTATED OBJECTS" value={totalObjects} detail="actual annotations" accent="violet" />
        <StatCard icon={Tag} label="MOST USED CLASS" value={mostUsed?.name || '—'} detail={mostUsed ? `${mostUsed.usage_count} objects` : 'No usage yet'} accent="green" />
      </section>

      {error && <div className="feedback feedback--error page-feedback"><TriangleAlert size={17} /><span>{error}</span></div>}
      {success && <div className="feedback feedback--success page-feedback"><CheckCircle2 size={17} /><span>{success}</span></div>}

      <section className="classes-panel">
        <div className="classes-panel__header"><div><h2>Class definitions</h2><p>IDs are permanent and will be referenced by future annotations.</p></div><span>{classes.length} total</span></div>
        {loading ? (
          <div className="classes-empty"><span className="spinner" /> Loading classes...</div>
        ) : classes.length ? (
          <div className="class-table-wrap">
            <table className="class-table">
              <thead><tr><th>Class name</th><th>ID</th><th>Usage</th><th>Created</th><th><span className="visually-hidden">Actions</span></th></tr></thead>
              <tbody>{classes.map((record) => (
                <tr key={record.id}>
                  <td><span className="class-color" style={{ backgroundColor: record.color, boxShadow: `0 0 12px ${record.color}35` }} /><strong>{record.name}</strong><code>{record.color}</code></td>
                  <td><span className="class-id">{record.id}</span></td>
                  <td><span className="usage-count"><Box size={14} /> {record.usage_count} object{record.usage_count === 1 ? '' : 's'}</span></td>
                  <td>{formatDate(record.created_at)}</td>
                  <td><div className="row-actions"><button type="button" disabled={locked} aria-label={`Edit ${record.name}`} onClick={() => openEdit(record)}><Edit3 size={15} /></button><button className="danger" type="button" disabled={locked} aria-label={`Delete ${record.name}`} onClick={() => { clearFeedback(); setDeleting(record) }}><Trash2 size={15} /></button></div></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : (
          <div className="classes-empty"><span className="classes-empty__icon"><Layers3 size={28} /></span><strong>No classes configured</strong><p>Create classes before starting annotation.</p><button className="create-button" type="button" disabled={locked} onClick={openCreate}><Plus size={17} /> Add class</button></div>
        )}
      </section>

      {editing !== undefined && <ClassDialog record={editing} saving={saving} error={error} onClose={() => setEditing(undefined)} onSubmit={(data) => editing ? edit(editing.id, data) : add(data)} />}
      {deleting && <DeleteClassDialog record={deleting} saving={saving} error={error} onClose={() => setDeleting(null)} onConfirm={async () => { if (await remove(deleting)) setDeleting(null) }} />}
    </div>
  )
}
