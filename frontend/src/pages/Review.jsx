import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, ClipboardCheck, Filter, TriangleAlert, X } from 'lucide-react'

import { acceptPrediction, datasetThumbnailUrl, editPrediction, fetchAnnotations, fetchReviewItem, fetchReviewQueue, rejectPrediction, acceptReviewPredictions, rejectReviewPredictions } from '../api/client'
import { AnnotationCanvas } from '../components/annotation/AnnotationCanvas'
import { ActiveLearning } from '../components/review/ActiveLearning'

const confidenceMatches = (item, filter) => filter === 'all' || (filter === 'high' ? item.has_high_confidence : filter === 'medium' ? item.has_medium_confidence : item.has_low_confidence)

export function Review({ projectId, classes, onAnnotationsChanged }) {
  const [queue, setQueue] = useState({ items: [], summary: {}, model_ids: [] })
  const [selectedKey, setSelectedKey] = useState('')
  const [detail, setDetail] = useState(null)
  const [annotations, setAnnotations] = useState([])
  const [selectedPredictionId, setSelectedPredictionId] = useState(null)
  const [confidenceFilter, setConfidenceFilter] = useState('all')
  const [modelFilter, setModelFilter] = useState('all')
  const [sort, setSort] = useState('lowest')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState('all')

  const reloadQueue = useCallback(async () => {
    const result = await fetchReviewQueue()
    setQueue(result)
    return result
  }, [])

  useEffect(() => { let active = true; fetchReviewQueue().then((result) => { if (active) { setQueue(result); setSelectedKey(''); setDetail(null); setError('') } }).catch((requestError) => { if (active) setError(requestError.message) }); return () => { active = false } }, [projectId])

  const items = useMemo(() => queue.items.filter((item) => item.status !== 'REVIEWED' && (modelFilter === 'all' || item.model_id === modelFilter) && confidenceMatches(item, confidenceFilter)).sort((left, right) => sort === 'highest' ? right.highest_confidence - left.highest_confidence : sort === 'count' ? right.pending_count - left.pending_count : sort === 'filename' ? left.filename.localeCompare(right.filename) : sort === 'newest' ? new Date(right.newest_prediction_at) - new Date(left.newest_prediction_at) : left.lowest_confidence - right.lowest_confidence), [queue.items, modelFilter, confidenceFilter, sort])
  const matchedIndex = items.findIndex((item) => item.key === selectedKey)
  const selectedIndex = matchedIndex >= 0 ? matchedIndex : 0
  const selectedItem = items[selectedIndex] || null

  useEffect(() => {
    if (!selectedItem) return
    let active = true
    Promise.all([fetchReviewItem(selectedItem.image_id, selectedItem.model_id, selectedItem.prediction_run_id), fetchAnnotations(selectedItem.image_id)]).then(([review, human]) => { if (active) { setDetail(review); setAnnotations(human.annotations); setSelectedPredictionId(review.predictions.find((item) => item.status === 'pending')?.id || null); setError('') } }).catch((requestError) => { if (active) setError(requestError.message) })
    return () => { active = false }
  }, [selectedItem])

  const refreshCurrent = useCallback(async () => {
    const result = await reloadQueue()
    const stillPending = result.items.find((item) => item.key === selectedKey && item.status !== 'REVIEWED')
    if (stillPending) {
      const [review, human] = await Promise.all([fetchReviewItem(stillPending.image_id, stillPending.model_id, stillPending.prediction_run_id), fetchAnnotations(stillPending.image_id)])
      setDetail(review); setAnnotations(human.annotations)
    }
    await onAnnotationsChanged?.()
  }, [onAnnotationsChanged, reloadQueue, selectedKey])

  const act = async (operation) => { setBusy(true); setError(''); try { await operation(); await refreshCurrent() } catch (requestError) { setError(requestError.message) } finally { setBusy(false) } }
  const updatePrediction = async (next) => { const record = await editPrediction(next.id, { class_id: next.class_id, x1: next.x1, y1: next.y1, x2: next.x2, y2: next.y2 }); setDetail((current) => ({ ...current, predictions: current.predictions.map((item) => item.id === record.id ? record : item) })) }
  const previewPrediction = (next) => setDetail((current) => ({ ...current, predictions: current.predictions.map((item) => item.id === next.id ? next : item) }))
  const pending = detail?.predictions.filter((item) => item.status === 'pending') || []
  const selectedPrediction = pending.find((item) => item.id === selectedPredictionId) || null
  const classById = new Map(classes.map((item) => [item.id, item]))
  const move = (offset) => { const next = selectedIndex + offset; if (next >= 0 && next < items.length) { setSelectedKey(items[next].key); setSelectedPredictionId(null) } }

  const modeSwitch = <div className="review-mode"><button className={mode==='all'?'active':''} type="button" onClick={()=>setMode('all')}>All Predictions</button><button className={mode==='active'?'active':''} type="button" onClick={()=>setMode('active')}>Active Learning</button></div>

  if(mode==='active') return <div className="review-page"><header className="page-heading"><div><span className="eyebrow">HUMAN-IN-THE-LOOP</span><h1>Review</h1><p>Accept, correct, or reject stored model predictions before they become annotations.</p></div></header>{modeSwitch}<ActiveLearning projectId={projectId} onReview={(key)=>{setSelectedKey(key);setMode('all')}}/></div>

  return <div className="review-page">
    <header className="page-heading"><div><span className="eyebrow">HUMAN-IN-THE-LOOP</span><h1>Review</h1><p>Accept, correct, or reject stored model predictions before they become annotations.</p></div></header>
    {modeSwitch}
    <section className="review-progress">{[['Pending',queue.summary.pending_images],['Reviewed',queue.summary.reviewed_images],['Accepted',queue.summary.accepted],['Edited',queue.summary.edited],['Rejected',queue.summary.rejected]].map(([label,value]) => <div key={label}><span>{label}</span><strong>{value || 0}</strong></div>)}</section>
    <section className="review-filters"><Filter size={15}/><label>Confidence<select value={confidenceFilter} onChange={(event) => setConfidenceFilter(event.target.value)}><option value="all">All</option><option value="high">High (≥ 0.75)</option><option value="medium">Medium (0.40–0.75)</option><option value="low">Low (&lt; 0.40)</option></select></label><label>Model<select value={modelFilter} onChange={(event) => setModelFilter(event.target.value)}><option value="all">All models</option>{queue.model_ids.map((id) => <option key={id}>{id}</option>)}</select></label><label>Sort<select value={sort} onChange={(event) => setSort(event.target.value)}><option value="lowest">Lowest confidence first</option><option value="highest">Highest confidence first</option><option value="count">Number of predictions</option><option value="filename">Filename</option><option value="newest">Newest prediction run</option></select></label></section>
    {error && <div className="annotation-feedback error"><TriangleAlert size={15}/>{error}</div>}
    {!items.length ? <section className="review-empty"><ClipboardCheck size={32}/><h2>Review queue is clear</h2><p>No pending predictions match the current filters.</p></section> : <div className="review-layout">
      <aside className="review-queue">{items.map((item) => <button type="button" className={item.key === selectedItem?.key ? 'active' : ''} key={item.key} onClick={() => setSelectedKey(item.key)}><img src={datasetThumbnailUrl(item.image_id)} alt=""/><span><strong>{item.filename}</strong><small>{item.pending_count} pending · highest {item.highest_confidence.toFixed(4)} · avg {item.average_confidence.toFixed(4)}</small><small>{item.model_id}</small><em>{item.status.replace('_',' ')}</em></span></button>)}</aside>
      <main className="review-workspace">{detail && <><header><div><h2>{detail.item.filename}</h2><small>{detail.item.model_id} · run {detail.item.prediction_run_id}</small></div><span>Review image {selectedIndex + 1} / {items.length}</span></header><div className="review-canvas"><AnnotationCanvas image={detail.item} classes={classes} annotations={annotations} predictions={pending} selectedClassId={null} selectedAnnotationId={null} selectedPredictionId={selectedPredictionId} onSelectAnnotation={() => {}} onSelectPrediction={setSelectedPredictionId} onPreview={() => {}} onChange={() => {}} onPredictionPreview={previewPrediction} onPredictionChange={updatePrediction} annotationReadOnly predictionReadOnly={busy}/></div><footer><button type="button" disabled={selectedIndex === 0} onClick={() => move(-1)}><ArrowLeft size={14}/>Previous</button><div><button type="button" disabled={!pending.length || busy} onClick={() => act(() => acceptReviewPredictions(pending.map((item) => item.id)))}><Check size={14}/>Accept All Predictions</button><button className="reject" type="button" disabled={!pending.length || busy} onClick={() => act(() => rejectReviewPredictions(pending.map((item) => item.id)))}><X size={14}/>Reject All Predictions</button></div><button type="button" disabled={selectedIndex === items.length - 1} onClick={() => move(1)}>Next<ArrowRight size={14}/></button></footer></>}</main>
      <aside className="review-actions"><h3>Predictions</h3>{pending.map((prediction) => <button type="button" className={selectedPredictionId === prediction.id ? 'active' : ''} key={prediction.id} onClick={() => setSelectedPredictionId(prediction.id)}><i style={{backgroundColor:classById.get(prediction.class_id)?.color}}/><span>{classById.get(prediction.class_id)?.name}<small>{prediction.confidence.toFixed(3)}</small></span></button>)}{selectedPrediction && <section><label>Class<select value={selectedPrediction.class_id} disabled={busy} onChange={(event) => act(() => editPrediction(selectedPrediction.id,{class_id:Number(event.target.value)}))}>{classes.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label><div><button type="button" disabled={busy} onClick={() => act(() => acceptPrediction(selectedPrediction.id))}><Check size={13}/>Accept</button><button type="button" disabled={busy} onClick={() => act(() => rejectPrediction(selectedPrediction.id))}><X size={13}/>Reject</button></div><p>Move or resize the dashed box on the canvas, change its class, then accept.</p></section>}<dl><div><dt>Predictions</dt><dd>{detail?.item.prediction_count || 0}</dd></div><div><dt>Accepted</dt><dd>{detail?.item.accepted_count || 0}</dd></div><div><dt>Edited</dt><dd>{detail?.item.edited_count || 0}</dd></div><div><dt>Rejected</dt><dd>{detail?.item.rejected_count || 0}</dd></div><div><dt>Permanent annotations added</dt><dd>{detail?.item.permanent_annotations_added || 0}</dd></div></dl></aside>
    </div>}
  </div>
}
