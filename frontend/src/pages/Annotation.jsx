import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, Boxes, Check, Cpu, Database, MousePointer2, Play, Save, Tag, Trash2, TriangleAlert, X } from 'lucide-react'

import { datasetThumbnailUrl } from '../api/client'
import { AnnotationCanvas } from '../components/annotation/AnnotationCanvas'
import { UnsavedDialog } from '../components/annotation/UnsavedDialog'
import { useAnnotations } from '../hooks/useAnnotations'
import { usePredictions } from '../hooks/usePredictions'

export const Annotation = forwardRef(function Annotation({ dataset, classState, onNavigate, onSaved, locked = false, projectId }, ref) {
  const { images, loading: datasetLoading } = dataset
  const { classes, loading: classesLoading } = classState
  const [imageIndex, setImageIndex] = useState(0)
  const [selectedClassId, setSelectedClassId] = useState(classes[0]?.id ?? null)
  const [selectedAnnotationId, setSelectedAnnotationId] = useState(null)
  const [pendingIndex, setPendingIndex] = useState(null)
  const [cancelSignal, setCancelSignal] = useState(0)
  const [confidence, setConfidence] = useState(.25)
  const [maxDetections, setMaxDetections] = useState(100)
  const [predictionSort, setPredictionSort] = useState('confidence-desc')
  const [selectedPredictionId, setSelectedPredictionId] = useState(null)
  const currentImage = images[imageIndex] || null
  const annotationState = useAnnotations(currentImage?.id, onSaved)
  const { annotations, updateDraft, previewDraft, loading, saving, dirty, error, saveStatus, save, flush, retry, reload } = annotationState
  const predictionState = usePredictions(projectId, currentImage?.id, reload)
  const { setPredictions, update: updatePrediction } = predictionState
  const classById = useMemo(() => new Map(classes.map((record) => [record.id, record])), [classes])
  const visiblePredictions = useMemo(() => predictionState.predictions
    .filter((item) => item.status === 'pending' && item.confidence >= confidence)
    .sort((left, right) => predictionSort === 'confidence-asc'
      ? left.confidence - right.confidence
      : predictionSort === 'class'
        ? (classById.get(left.class_id)?.name || '').localeCompare(classById.get(right.class_id)?.name || '') || right.confidence - left.confidence
        : right.confidence - left.confidence), [predictionState.predictions, confidence, predictionSort, classById])
  const selectedPrediction = visiblePredictions.find((item) => item.id === selectedPredictionId) || null
  const previewPrediction = useCallback((next) => {
    setPredictions((current) => current.map((item) => item.id === next.id ? next : item))
  }, [setPredictions])
  const commitPrediction = useCallback((next) => {
    updatePrediction(next.id, { class_id: next.class_id, x1: next.x1, y1: next.y1, x2: next.x2, y2: next.y2 })
  }, [updatePrediction])
  useImperativeHandle(ref, () => ({ dirty, save: flush }), [dirty, flush])

  const selectedAnnotation = annotations.find((annotation) => annotation.id === selectedAnnotationId) || null

  const switchImage = useCallback((nextIndex) => {
    setImageIndex(nextIndex)
    setSelectedAnnotationId(null)
    setSelectedPredictionId(null)
  }, [])

  const requestImage = useCallback(async (nextIndex) => {
    if (nextIndex < 0 || nextIndex >= images.length || nextIndex === imageIndex) return
    if (dirty) {
      if (await flush()) switchImage(nextIndex)
      else setPendingIndex(nextIndex)
    } else switchImage(nextIndex)
  }, [dirty, flush, imageIndex, images.length, switchImage])

  const deleteSelected = useCallback(() => {
    if (locked || !selectedAnnotationId) return
    updateDraft((current) => current.filter((annotation) => annotation.id !== selectedAnnotationId))
    setSelectedAnnotationId(null)
  }, [locked, selectedAnnotationId, updateDraft])

  useEffect(() => {
    const handleKey = (event) => {
      const target = event.target
      if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) return
      if (event.key === 'ArrowLeft') requestImage(imageIndex - 1)
      if (event.key === 'ArrowRight') requestImage(imageIndex + 1)
      if (event.key === 'Delete') deleteSelected()
      if (event.key === 'Escape') setCancelSignal((value) => value + 1)
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [deleteSelected, imageIndex, requestImage])

  const continueAfterSave = async () => {
    if (await flush()) { switchImage(pendingIndex); setPendingIndex(null) }
  }

  if (datasetLoading || classesLoading) return <div className="annotation-gate"><span className="spinner" /> Loading annotation workspace...</div>
  if (!images.length) return <div className="annotation-gate"><span className="annotation-gate__icon"><Database size={30} /></span><h1>No images available</h1><p>Import a dataset before starting annotation.</p><button className="create-button" type="button" onClick={() => onNavigate('Dataset')}>Open Dataset</button></div>
  if (!classes.length) return <div className="annotation-gate"><span className="annotation-gate__icon"><Tag size={30} /></span><h1>No classes configured</h1><p>Create at least one class before annotating.</p><button className="create-button" type="button" onClick={() => onNavigate('Classes')}>Open Classes</button></div>

  return <div className="annotation-page">
    <aside className="annotation-images-panel">
      <div className="annotation-panel-title"><span>IMAGES</span><strong>{images.length}</strong></div>
      <div className="annotation-thumbnails">{images.map((image, index) => <button className={`annotation-thumbnail${index === imageIndex ? ' active' : ''}`} type="button" key={image.id} onClick={() => requestImage(index)}><img src={datasetThumbnailUrl(image.id)} alt="" loading="lazy" /><span><strong title={image.filename}>{image.filename}</strong><small className={image.annotation_count ? 'complete' : ''}>{image.annotation_count || 0} object{image.annotation_count === 1 ? '' : 's'}</small></span></button>)}</div>
    </aside>

    <section className="annotation-workspace">
      <header className="annotation-workspace__header"><div><span className="eyebrow">ANNOTATION EDITOR</span><h1>{currentImage.filename}</h1></div><span>{currentImage.width} × {currentImage.height}px</span></header>
      <div className="annotation-canvas-area">
        {loading ? <div className="canvas-loading"><span className="spinner" /> Loading annotations...</div> : <AnnotationCanvas key={`${currentImage.id}-${cancelSignal}`} image={currentImage} classes={classes} annotations={annotations} predictions={visiblePredictions} selectedClassId={selectedClassId} selectedAnnotationId={selectedAnnotationId} selectedPredictionId={selectedPredictionId} onSelectAnnotation={setSelectedAnnotationId} onSelectPrediction={setSelectedPredictionId} onPreview={previewDraft} onChange={updateDraft} onPredictionPreview={previewPrediction} onPredictionChange={commitPrediction} readOnly={locked || predictionState.running} />}
      </div>
      <footer className="annotation-footer">
        <button className="footer-nav" type="button" disabled={imageIndex === 0} onClick={() => requestImage(imageIndex - 1)}><ArrowLeft size={16} /> Previous</button>
        <span>Image <strong>{imageIndex + 1}</strong> / {images.length}</span>
        <button className="footer-nav" type="button" disabled={imageIndex === images.length - 1} onClick={() => requestImage(imageIndex + 1)}>Next <ArrowRight size={16} /></button>
        <div className={`auto-save-status auto-save-status--${saveStatus}`}><span>{saveStatus === 'saved' ? '✓' : saveStatus === 'unsaved' ? '●' : saveStatus === 'saving' ? '⟳' : '⚠'}</span>{saveStatus === 'saved' ? 'Saved' : saveStatus === 'unsaved' ? 'Unsaved changes' : saveStatus === 'saving' ? 'Saving...' : 'Save failed'}{saveStatus === 'failed' && <button type="button" onClick={retry}>Retry</button>}</div>
        <button className="save-annotation-button" type="button" disabled={locked || saving || !dirty} onClick={save}><Save size={16} /> Save</button>
      </footer>
    </section>

    <aside className="annotation-tools-panel">
      <div className="annotation-panel-section prediction-model-panel"><div className="annotation-panel-title"><span>MODEL</span><Cpu size={13} /></div>{predictionState.models.length ? <><label className="annotation-class-select"><span>Current model</span><select value={predictionState.modelId} onChange={(event) => predictionState.setModelId(event.target.value)}>{predictionState.models.map((model) => <option key={model.id} value={model.id}>{model.id}</option>)}</select></label><label className="prediction-threshold"><span>Confidence threshold</span><strong>{confidence.toFixed(2)}</strong><input type="range" min="0.05" max="0.95" step="0.05" value={confidence} onChange={(event) => setConfidence(Number(event.target.value))} /></label>{confidence < .1 && <p className="prediction-threshold-warning"><TriangleAlert size={12} />Very low confidence thresholds may produce many false-positive predictions.</p>}<label className="annotation-class-select"><span>Maximum detections per image</span><select value={maxDetections} onChange={(event) => setMaxDetections(Number(event.target.value))}>{[25,50,100,200].map((value) => <option value={value} key={value}>{value}</option>)}</select></label><button className="prediction-action" type="button" disabled={predictionState.running} onClick={() => predictionState.run('current',confidence,maxDetections)}><Play size={13} /> Predict current image</button><button className="prediction-action secondary" type="button" disabled={predictionState.running || !dataset.stats.unannotated_images} onClick={() => {if(window.confirm(`Run ${predictionState.modelId} on ${dataset.stats.unannotated_images} unannotated images at confidence ${confidence.toFixed(2)}, limited to ${maxDetections} detections per image?`))predictionState.run('unannotated',confidence,maxDetections)}}>Predict {dataset.stats.unannotated_images} unannotated</button></> : <p className="panel-hint">No trained model available. Train a model first to enable automatic labeling.</p>}</div>
      <div className="annotation-panel-section"><div className="annotation-panel-title"><span>CLASSES</span><strong>{classes.length}</strong></div><p className="panel-hint"><MousePointer2 size={13} /> Select a class, then drag on the image.</p><div className="annotation-class-list">{classes.map((record) => <button className={selectedClassId === record.id ? 'active' : ''} type="button" key={record.id} onClick={() => setSelectedClassId(record.id)}><i style={{ backgroundColor: record.color }} /><span>{record.name}</span><small>ID {record.id}</small></button>)}</div></div>
      <div className="annotation-panel-section current-objects"><div className="annotation-panel-title"><span>CURRENT IMAGE</span><strong>{annotations.length}</strong></div>{annotations.length ? <div className="object-list">{annotations.map((annotation, index) => { const record = classById.get(annotation.class_id); return <button className={selectedAnnotationId === annotation.id ? 'active' : ''} type="button" key={annotation.id} onClick={() => setSelectedAnnotationId(annotation.id)}><span className="object-number">{index + 1}</span><i style={{ backgroundColor: record?.color }} /><span>{record?.name || `Class ${annotation.class_id}`}</span></button> })}</div> : <div className="objects-empty"><Boxes size={22} /><span>No boxes on this image</span></div>}</div>
      <div className="annotation-panel-section prediction-list"><div className="annotation-panel-title"><span>MODEL PREDICTIONS</span><strong>{visiblePredictions.length}</strong></div><label className="prediction-sort"><span>Sort</span><select value={predictionSort} onChange={(event) => setPredictionSort(event.target.value)}><option value="confidence-desc">Confidence: highest first</option><option value="confidence-asc">Confidence: lowest first</option><option value="class">Class</option></select></label>{visiblePredictions.length ? <><div className="object-list">{visiblePredictions.map((prediction) => <button className={selectedPredictionId===prediction.id?'active':''} type="button" key={prediction.id} onClick={()=>{setSelectedPredictionId(prediction.id);setSelectedAnnotationId(null)}}><i style={{backgroundColor:classById.get(prediction.class_id)?.color}} /><span>{classById.get(prediction.class_id)?.name}</span><small>{(prediction.confidence*100).toFixed(1)}%</small></button>)}</div><button className="prediction-accept-all" type="button" onClick={()=>predictionState.accept(visiblePredictions.map(item=>item.id))}><Check size={13}/> Accept all</button></> : <div className="objects-empty"><Cpu size={20}/><span>{predictionState.job?.state==='COMPLETED'?'No objects detected above threshold.':'No active predictions'}</span></div>}</div>
      {selectedAnnotation && <div className="selected-object-card"><span className="eyebrow">SELECTED OBJECT</span><strong><i style={{ backgroundColor: classById.get(selectedAnnotation.class_id)?.color }} />{classById.get(selectedAnnotation.class_id)?.name}</strong><label className="annotation-class-select"><span>Assigned class</span><select disabled={locked} value={selectedAnnotation.class_id} onChange={(event) => updateDraft((current) => current.map((annotation) => annotation.id === selectedAnnotation.id ? { ...annotation, class_id: Number(event.target.value) } : annotation))}>{classes.map((record) => <option value={record.id} key={record.id}>{record.name}</option>)}</select></label><dl><div><dt>X1 / Y1</dt><dd>{Math.round(selectedAnnotation.x1)} / {Math.round(selectedAnnotation.y1)}</dd></div><div><dt>X2 / Y2</dt><dd>{Math.round(selectedAnnotation.x2)} / {Math.round(selectedAnnotation.y2)}</dd></div><div><dt>Width / Height</dt><dd>{Math.round(selectedAnnotation.x2-selectedAnnotation.x1)} / {Math.round(selectedAnnotation.y2-selectedAnnotation.y1)}</dd></div></dl><button className="delete-annotation-button" type="button" disabled={locked} onClick={deleteSelected}><Trash2 size={15} /> Delete annotation</button></div>}
      {selectedPrediction && <div className="selected-object-card prediction-card"><span className="eyebrow">SELECTED PREDICTION · {Math.round(selectedPrediction.confidence*100)}%</span><strong><i style={{backgroundColor:classById.get(selectedPrediction.class_id)?.color}} />{classById.get(selectedPrediction.class_id)?.name}</strong><label className="annotation-class-select"><span>Assigned class</span><select value={selectedPrediction.class_id} onChange={(event)=>predictionState.update(selectedPrediction.id,{class_id:Number(event.target.value)})}>{classes.map(record=><option value={record.id} key={record.id}>{record.name}</option>)}</select></label><div className="prediction-review-actions"><button type="button" onClick={()=>predictionState.accept([selectedPrediction.id])}><Check size={13}/> Accept</button><button type="button" onClick={()=>predictionState.reject(selectedPrediction.id)}><X size={13}/> Reject</button></div></div>}
      {predictionState.job && <div className="annotation-panel-section prediction-console"><div className="annotation-panel-title"><span>PREDICTION · {predictionState.job.state}</span>{predictionState.running&&<button type="button" onClick={predictionState.cancel}>Cancel</button>}</div><p>Processed {predictionState.job.processed} / {predictionState.job.total}</p><dl className="prediction-quality-summary"><div><dt>Predictions</dt><dd>{predictionState.job.prediction_count}</dd></div><div><dt>Images with predictions</dt><dd>{predictionState.job.images_with_predictions}</dd></div><div><dt>Images without predictions</dt><dd>{predictionState.job.images_without_predictions}</dd></div><div><dt>Average confidence</dt><dd>{predictionState.job.average_confidence == null ? '—' : predictionState.job.average_confidence.toFixed(3)}</dd></div><div><dt>Highest confidence</dt><dd>{predictionState.job.highest_confidence == null ? '—' : predictionState.job.highest_confidence.toFixed(3)}</dd></div><div><dt>Lowest confidence</dt><dd>{predictionState.job.lowest_confidence == null ? '—' : predictionState.job.lowest_confidence.toFixed(3)}</dd></div></dl><div>{predictionState.logs.slice(-5).map((entry,index)=><small key={`${entry.timestamp}-${index}`}>[{entry.timestamp}] {entry.message}</small>)}</div></div>}
      {predictionState.error && <div className="annotation-feedback error"><TriangleAlert size={15}/>{predictionState.error}</div>}
      {locked && <div className="annotation-feedback error"><TriangleAlert size={15} />Annotation editing is paused while training uses this project snapshot.</div>}
      {error && <div className="annotation-feedback error"><TriangleAlert size={15} />{error}</div>}
    </aside>
    {pendingIndex != null && <UnsavedDialog saving={saving} onCancel={() => setPendingIndex(null)} onDiscard={() => { switchImage(pendingIndex); setPendingIndex(null) }} onSave={continueAfterSave} />}
  </div>
})
