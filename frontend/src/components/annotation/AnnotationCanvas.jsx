import { memo, useCallback, useEffect, useRef, useState } from 'react'

import { datasetImageUrl } from '../../api/client'

const MIN_BOX_SIZE = 3

function moveBox(original, start, point, image) {
  const width = original.x2 - original.x1
  const height = original.y2 - original.y1
  const x1 = Math.max(0, Math.min(image.width - width, original.x1 + point.x - start.x))
  const y1 = Math.max(0, Math.min(image.height - height, original.y1 + point.y - start.y))
  return { ...original, x1, y1, x2: x1 + width, y2: y1 + height }
}

function resizeBox(original, corner, point, image) {
  const box = { ...original }
  if (corner.includes('l')) box.x1 = Math.max(0, Math.min(original.x2 - MIN_BOX_SIZE, point.x))
  if (corner.includes('r')) box.x2 = Math.min(image.width, Math.max(original.x1 + MIN_BOX_SIZE, point.x))
  if (corner.includes('t')) box.y1 = Math.max(0, Math.min(original.y2 - MIN_BOX_SIZE, point.y))
  if (corner.includes('b')) box.y2 = Math.min(image.height, Math.max(original.y1 + MIN_BOX_SIZE, point.y))
  return box
}

export const AnnotationCanvas = memo(function AnnotationCanvas({ image, classes, annotations, predictions = [], selectedClassId, selectedAnnotationId, selectedPredictionId, onSelectAnnotation, onSelectPrediction, onPreview, onChange, onPredictionPreview, onPredictionChange, readOnly = false }) {
  const imageRef = useRef(null)
  const overlayRef = useRef(null)
  const interactionRef = useRef(null)
  const [cursor, setCursor] = useState(null)
  const [drawing, setDrawing] = useState(null)

  useEffect(() => () => {
    if (interactionRef.current) {
      const original = interactionRef.current.original
      if (interactionRef.current.kind === 'prediction') onPredictionPreview(original)
      else onPreview((current) => current.map((item) => item.id === original.id ? original : item))
    }
  }, [onPredictionPreview, onPreview])

  const toImagePoint = useCallback((event) => {
    const rect = imageRef.current?.getBoundingClientRect()
    if (!rect?.width || !rect?.height) return null
    return {
      x: Math.max(0, Math.min(image.width, (event.clientX - rect.left) * image.width / rect.width)),
      y: Math.max(0, Math.min(image.height, (event.clientY - rect.top) * image.height / rect.height)),
    }
  }, [image.height, image.width])

  const capturePointer = (event) => overlayRef.current?.setPointerCapture(event.pointerId)

  const handlePointerDown = (event) => {
    if (readOnly || event.button !== 0 || selectedClassId == null) return
    const point = toImagePoint(event)
    if (!point) return
    capturePointer(event)
    onSelectAnnotation(null)
    onSelectPrediction?.(null)
    setDrawing({ start: point, current: point })
  }

  const beginInteraction = (event, annotation, type, corner = null) => {
    event.stopPropagation()
    if (readOnly || event.button !== 0) return
    const point = toImagePoint(event)
    if (!point) return
    capturePointer(event)
    onSelectAnnotation(annotation.id)
    onSelectPrediction?.(null)
    interactionRef.current = { kind: 'annotation', type, corner, id: annotation.id, start: point, original: { ...annotation }, latest: { ...annotation } }
  }

  const beginPredictionInteraction = (event, prediction, type, corner = null) => {
    event.stopPropagation()
    if (readOnly || event.button !== 0) return
    const point = toImagePoint(event)
    if (!point) return
    capturePointer(event)
    onSelectAnnotation(null)
    onSelectPrediction(prediction.id)
    interactionRef.current = { kind: 'prediction', type, corner, id: prediction.id, start: point, original: { ...prediction }, latest: { ...prediction } }
  }

  const calculateInteraction = (interaction, point) => interaction.type === 'move'
    ? moveBox(interaction.original, interaction.start, point, image)
    : resizeBox(interaction.original, interaction.corner, point, image)

  const handlePointerMove = (event) => {
    const point = toImagePoint(event)
    if (!point) return
    setCursor(point)
    if (interactionRef.current) {
      const nextBox = calculateInteraction(interactionRef.current, point)
      interactionRef.current.latest = nextBox
      if (interactionRef.current.kind === 'prediction') onPredictionPreview(nextBox)
      else onPreview((current) => current.map((item) => item.id === nextBox.id ? nextBox : item))
    } else if (drawing) {
      setDrawing({ ...drawing, current: point })
    }
  }

  const finishPointerAction = (event) => {
    if (interactionRef.current) {
      const point = toImagePoint(event)
      const finalBox = point ? calculateInteraction(interactionRef.current, point) : interactionRef.current.latest
      const kind = interactionRef.current.kind
      interactionRef.current = null
      if (kind === 'prediction') onPredictionChange(finalBox)
      else onChange((current) => current.map((item) => item.id === finalBox.id ? finalBox : item))
      return
    }
    if (!drawing) return
    const end = toImagePoint(event) || drawing.current
    const box = {
      id: `draft-${crypto.randomUUID()}`,
      image_id: image.id,
      class_id: selectedClassId,
      x1: Math.min(drawing.start.x, end.x), y1: Math.min(drawing.start.y, end.y),
      x2: Math.max(drawing.start.x, end.x), y2: Math.max(drawing.start.y, end.y),
    }
    setDrawing(null)
    if (box.x2 - box.x1 < MIN_BOX_SIZE || box.y2 - box.y1 < MIN_BOX_SIZE) return
    onChange((current) => [...current, box])
    onSelectAnnotation(box.id)
  }

  const cancelPointerAction = () => {
    if (interactionRef.current) {
      const original = interactionRef.current.original
      const kind = interactionRef.current.kind
      interactionRef.current = null
      if (kind === 'prediction') onPredictionPreview(original)
      else onPreview((current) => current.map((item) => item.id === original.id ? original : item))
    }
    setDrawing(null)
  }

  const classById = new Map(classes.map((record) => [record.id, record]))
  const draftBox = drawing && { x1: Math.min(drawing.start.x, drawing.current.x), y1: Math.min(drawing.start.y, drawing.current.y), x2: Math.max(drawing.start.x, drawing.current.x), y2: Math.max(drawing.start.y, drawing.current.y) }
  const handleRadius = Math.max(5, image.width / 260)

  return <div className="annotation-stage"><div className="annotation-image-wrap">
    <img ref={imageRef} src={datasetImageUrl(image.id)} alt={image.filename} draggable="false" />
    <svg ref={overlayRef} className={`annotation-overlay${selectedClassId == null || readOnly ? ' annotation-overlay--disabled' : ''}`} viewBox={`0 0 ${image.width} ${image.height}`} preserveAspectRatio="none" onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={finishPointerAction} onPointerCancel={cancelPointerAction} onPointerLeave={() => { if (!drawing && !interactionRef.current) setCursor(null) }}>
      {cursor && <><line className="axis-guide" x1={cursor.x} y1="0" x2={cursor.x} y2={image.height} vectorEffect="non-scaling-stroke" /><line className="axis-guide" x1="0" y1={cursor.y} x2={image.width} y2={cursor.y} vectorEffect="non-scaling-stroke" /></>}
      {predictions.map((prediction) => {
        const record = classById.get(prediction.class_id)
        const selected = prediction.id === selectedPredictionId
        const handles = [{ key: 'lt', x: prediction.x1, y: prediction.y1 }, { key: 'rt', x: prediction.x2, y: prediction.y1 }, { key: 'lb', x: prediction.x1, y: prediction.y2 }, { key: 'rb', x: prediction.x2, y: prediction.y2 }]
        return <g className="prediction-box" key={prediction.id} onPointerDown={(event) => beginPredictionInteraction(event, prediction, 'move')}><rect x={prediction.x1} y={prediction.y1} width={prediction.x2-prediction.x1} height={prediction.y2-prediction.y1} fill={`${record?.color || '#62A6FF'}10`} stroke={record?.color || '#62A6FF'} strokeWidth={selected?3:2} strokeDasharray="9 6" vectorEffect="non-scaling-stroke"/><text x={prediction.x1} y={Math.max(13,prediction.y1)} fill="#fff" fontSize={Math.max(12,image.width/110)} paintOrder="stroke" stroke="#07101b" strokeWidth="3">{record?.name || `Class ${prediction.class_id}`} · {Math.round(prediction.confidence*100)}%</text>{selected&&handles.map(handle=><circle className="resize-handle prediction-handle" key={handle.key} cx={handle.x} cy={handle.y} r={handleRadius} vectorEffect="non-scaling-stroke" onPointerDown={(event)=>beginPredictionInteraction(event,prediction,'resize',handle.key)}/>)}</g>
      })}
      {annotations.map((annotation) => {
        const record = classById.get(annotation.class_id)
        const selected = annotation.id === selectedAnnotationId
        const handles = [{ key: 'lt', x: annotation.x1, y: annotation.y1 }, { key: 'rt', x: annotation.x2, y: annotation.y1 }, { key: 'lb', x: annotation.x1, y: annotation.y2 }, { key: 'rb', x: annotation.x2, y: annotation.y2 }]
        return <g className="saved-box" key={annotation.id} onPointerDown={(event) => beginInteraction(event, annotation, 'move')}>
          <rect x={annotation.x1} y={annotation.y1} width={annotation.x2 - annotation.x1} height={annotation.y2 - annotation.y1} fill={`${record?.color || '#62A6FF'}18`} stroke={record?.color || '#62A6FF'} strokeWidth={selected ? 3 : 2} vectorEffect="non-scaling-stroke" />
          <text x={annotation.x1} y={Math.max(13, annotation.y1)} fill="#fff" fontSize={Math.max(12, image.width / 110)} paintOrder="stroke" stroke="#07101b" strokeWidth="3">{record?.name || `Class ${annotation.class_id}`}</text>
          {selected && <><rect className="selection-outline" x={annotation.x1} y={annotation.y1} width={annotation.x2 - annotation.x1} height={annotation.y2 - annotation.y1} vectorEffect="non-scaling-stroke" />{handles.map((handle) => <circle className="resize-handle" key={handle.key} cx={handle.x} cy={handle.y} r={handleRadius} vectorEffect="non-scaling-stroke" onPointerDown={(event) => beginInteraction(event, annotation, 'resize', handle.key)} />)}</>}
        </g>
      })}
      {draftBox && <rect className="draft-box" x={draftBox.x1} y={draftBox.y1} width={draftBox.x2 - draftBox.x1} height={draftBox.y2 - draftBox.y1} stroke={classById.get(selectedClassId)?.color || '#62A6FF'} vectorEffect="non-scaling-stroke" />}
    </svg>
    {cursor && <div className="coordinate-tooltip" style={{ left: `${cursor.x / image.width * 100}%`, top: `${cursor.y / image.height * 100}%` }}>{drawing ? <><span>X1 {Math.round(drawing.start.x)} · Y1 {Math.round(drawing.start.y)}</span><strong>X2 {Math.round(cursor.x)} · Y2 {Math.round(cursor.y)}</strong><span>W {Math.round(Math.abs(cursor.x - drawing.start.x))} · H {Math.round(Math.abs(cursor.y - drawing.start.y))}</span></> : <strong>X {Math.round(cursor.x)} · Y {Math.round(cursor.y)}</strong>}</div>}
  </div></div>
})
