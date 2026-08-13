import { useEffect, useState } from 'react'
import { Archive, CheckCircle2, Download, FileArchive, RefreshCw, TriangleAlert } from 'lucide-react'

import { createExport, exportDownloadUrl, fetchExportPreview } from '../api/client'

const labels = [['images', 'Images'], ['annotated_images', 'Annotated images'], ['objects', 'Objects'], ['classes', 'Classes'], ['train_images', 'Train images'], ['validation_images', 'Validation images']]

export function Export({ projectId }) {
  const [preview, setPreview] = useState(null)
  const [record, setRecord] = useState(null)
  const [state, setState] = useState('loading')
  const [error, setError] = useState('')

  const load = async () => {
    setState('loading'); setError(''); setRecord(null)
    try { setPreview(await fetchExportPreview()); setState('ready') }
    catch (requestError) { setError(String(requestError.message || requestError)); setState('error') }
  }
  useEffect(() => {
    let active = true
    fetchExportPreview().then((result) => { if (active) { setPreview(result); setState('ready') } }).catch((requestError) => { if (active) { setError(String(requestError.message || requestError)); setState('error') } })
    return () => { active = false }
  }, [projectId])

  const generate = async () => {
    setState('generating'); setError('')
    try { setRecord(await createExport()); setState('success') }
    catch (requestError) { setError(typeof requestError.message === 'string' ? requestError.message : 'Export validation failed'); setState('error') }
  }

  return <div className="dashboard export-page">
    <div className="page-heading"><div><span className="eyebrow">GENERATED ARTIFACT</span><h1>Export</h1><p>Create an immutable YOLO dataset ZIP from the active project's human annotations.</p></div><span className="export-local"><Archive size={16}/> Project-local export</span></div>
    {state === 'loading' && <div className="export-state"><span className="spinner"/><h2>Validating export snapshot</h2><p>Reading project images, classes, annotations, and training split metadata.</p></div>}
    {state !== 'loading' && preview && <>
      <section className="export-card"><div className="export-card__heading"><FileArchive size={21}/><div><h2>YOLO object-detection dataset</h2><p>{preview.source === 'latest-training-snapshot' ? 'Using the latest valid completed training snapshot.' : 'Using a deterministic split of current annotated images.'}</p>{preview.source_snapshot && <code>{preview.source_snapshot}</code>}</div></div><div className="export-stats">{labels.map(([key,label])=><div key={key}><span>{label}</span><strong>{preview.stats[key]}</strong></div>)}</div></section>
      {preview.issues.length > 0 && <section className="export-issues"><h2><TriangleAlert size={17}/> Export validation failed</h2>{preview.issues.map((issue,index)=><div key={`${issue.image_id}-${issue.annotation_id}-${index}`}><strong>{issue.image_id || 'Project'}</strong><span>{issue.message}</span></div>)}</section>}
      {!preview.stats.images && !preview.issues.length && <div className="export-state"><FileArchive size={30}/><h2>No annotated images</h2><p>Add human annotations before creating a YOLO export.</p></div>}
      {error && <div className="annotation-feedback error"><TriangleAlert size={15}/>{error}</div>}
      {state === 'success' && record && <section className="export-success"><CheckCircle2 size={22}/><div><h2>Export ready</h2><p>A new immutable export workspace was created as <code>{record.id}</code>.</p></div><a href={exportDownloadUrl(record.id)} download={record.filename}><Download size={15}/> Download ZIP</a></section>}
      <div className="export-actions"><button type="button" className="secondary" onClick={load} disabled={state === 'generating'}><RefreshCw size={14}/> Revalidate</button><button type="button" onClick={generate} disabled={state === 'generating' || preview.issues.length > 0 || !preview.stats.images}><FileArchive size={14}/>{state === 'generating' ? 'Generating…' : 'Generate new export'}</button></div>
    </>}
  </div>
}
