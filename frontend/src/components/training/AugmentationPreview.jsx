import { useEffect, useRef, useState } from 'react'

import { datasetImageUrl, fetchAnnotations } from '../../api/client'

const PREVIEW_DEBOUNCE = 250

function normalizedRotation(value) {
  return ((Number(value) % 360) + 360) % 360
}

function outputDimensions(width, height, rotation) {
  return rotation === 90 || rotation === 270 ? { width: height, height: width } : { width, height }
}

function transformPoint(x, y, sourceWidth, sourceHeight, rotation, horizontalFlip, verticalFlip) {
  const output = outputDimensions(sourceWidth, sourceHeight, rotation)
  let point
  if (rotation === 90) point = { x: sourceHeight - y, y: x }
  else if (rotation === 180) point = { x: sourceWidth - x, y: sourceHeight - y }
  else if (rotation === 270) point = { x: y, y: sourceWidth - x }
  else point = { x, y }
  if (horizontalFlip) point.x = output.width - point.x
  if (verticalFlip) point.y = output.height - point.y
  return point
}

function transformedBox(annotation, sourceWidth, sourceHeight, config) {
  const rotation = normalizedRotation(config.rotation)
  const corners = [
    transformPoint(annotation.x1, annotation.y1, sourceWidth, sourceHeight, rotation, config.horizontal_flip, config.vertical_flip),
    transformPoint(annotation.x2, annotation.y1, sourceWidth, sourceHeight, rotation, config.horizontal_flip, config.vertical_flip),
    transformPoint(annotation.x1, annotation.y2, sourceWidth, sourceHeight, rotation, config.horizontal_flip, config.vertical_flip),
    transformPoint(annotation.x2, annotation.y2, sourceWidth, sourceHeight, rotation, config.horizontal_flip, config.vertical_flip),
  ]
  return {
    ...annotation,
    x1: Math.min(...corners.map((point) => point.x)), y1: Math.min(...corners.map((point) => point.y)),
    x2: Math.max(...corners.map((point) => point.x)), y2: Math.max(...corners.map((point) => point.y)),
  }
}

function drawBoxes(context, annotations, classes, width) {
  const classById = new Map(classes.map((record) => [record.id, record]))
  const lineWidth = Math.max(2, width / 350)
  context.font = `${Math.max(12, width / 50)}px system-ui`
  context.lineWidth = lineWidth
  annotations.forEach((annotation) => {
    const record = classById.get(annotation.class_id)
    const color = record?.color || '#62A6FF'
    context.strokeStyle = color
    context.fillStyle = `${color}22`
    context.fillRect(annotation.x1, annotation.y1, annotation.x2 - annotation.x1, annotation.y2 - annotation.y1)
    context.strokeRect(annotation.x1, annotation.y1, annotation.x2 - annotation.x1, annotation.y2 - annotation.y1)
    const label = record?.name || `Class ${annotation.class_id}`
    const metrics = context.measureText(label)
    const labelHeight = Math.max(18, width / 35)
    context.fillStyle = color
    context.fillRect(annotation.x1, Math.max(0, annotation.y1 - labelHeight), metrics.width + 10, labelHeight)
    context.fillStyle = '#07101b'
    context.fillText(label, annotation.x1 + 5, Math.max(labelHeight - 4, annotation.y1 - 4))
  })
}

function applyPixelation(canvas, strength) {
  if (!strength) return
  const context = canvas.getContext('2d')
  const scale = Math.max(0.03, 1 - strength / 105)
  const small = document.createElement('canvas')
  small.width = Math.max(1, Math.round(canvas.width * scale))
  small.height = Math.max(1, Math.round(canvas.height * scale))
  small.getContext('2d').drawImage(canvas, 0, 0, small.width, small.height)
  context.imageSmoothingEnabled = false
  context.clearRect(0, 0, canvas.width, canvas.height)
  context.drawImage(small, 0, 0, canvas.width, canvas.height)
  context.imageSmoothingEnabled = true
}

function applyNoise(canvas, amount, seed = 0) {
  if (!amount) return
  const context = canvas.getContext('2d')
  const imageData = context.getImageData(0, 0, canvas.width, canvas.height)
  const strength = amount * 1.2
  let randomState = seed || 123456789
  for (let index = 0; index < imageData.data.length; index += 4) {
    randomState = Math.imul(1664525, randomState) + 1013904223 | 0
    const noise = ((randomState >>> 0) / 4294967296 - 0.5) * strength
    imageData.data[index] += noise
    imageData.data[index + 1] += noise
    imageData.data[index + 2] += noise
  }
  context.putImageData(imageData, 0, 0)
}

function renderPreview(canvas, image, annotations, classes, config, augmented) {
  const rotation = augmented && config.enabled ? normalizedRotation(config.rotation) : 0
  const transformed = outputDimensions(image.naturalWidth, image.naturalHeight, rotation)
  canvas.width = transformed.width
  canvas.height = transformed.height
  const context = canvas.getContext('2d')
  context.save()
  if (augmented && config.enabled) {
    if (config.horizontal_flip) { context.translate(transformed.width, 0); context.scale(-1, 1) }
    if (config.vertical_flip) { context.translate(0, transformed.height); context.scale(1, -1) }
    if (rotation === 90) { context.translate(image.naturalHeight, 0); context.rotate(Math.PI / 2) }
    else if (rotation === 180) { context.translate(image.naturalWidth, image.naturalHeight); context.rotate(Math.PI) }
    else if (rotation === 270) { context.translate(0, image.naturalWidth); context.rotate(-Math.PI / 2) }
    const hueDegrees = Math.abs(config.hue) <= 0.1 ? config.hue * 180 : config.hue
    context.filter = `brightness(${config.brightness}) contrast(${config.contrast}) saturate(${config.grayscale ? 0 : config.saturation}) hue-rotate(${hueDegrees}deg) blur(${config.blur}px)`
  }
  context.drawImage(image, 0, 0)
  context.restore()
  if (augmented && config.enabled) {
    applyPixelation(canvas, config.pixelation)
    applyNoise(canvas, config.noise, config.noise_seed)
  }
  const boxes = augmented && config.enabled
    ? annotations.map((annotation) => transformedBox(annotation, image.naturalWidth, image.naturalHeight, config))
    : annotations
  drawBoxes(context, boxes, classes, transformed.width)
}

export function AugmentationPreview({ image, classes, config }) {
  const originalRef = useRef(null)
  const augmentedRef = useRef(null)
  const [annotations, setAnnotations] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    if (!image) return
    let active = true
    fetchAnnotations(image.id).then((result) => { if (active) setAnnotations(result.annotations) }).catch((requestError) => { if (active) setError(requestError.message || 'Preview annotations could not be loaded') })
    return () => { active = false }
  }, [image])

  useEffect(() => {
    if (!image) return
    const timer = setTimeout(() => {
      const source = new Image()
      source.crossOrigin = 'anonymous'
      source.onload = () => {
        renderPreview(originalRef.current, source, annotations, classes, config, false)
        renderPreview(augmentedRef.current, source, annotations, classes, config, true)
        setError('')
      }
      source.onerror = () => setError('The sample image could not be loaded')
      source.src = datasetImageUrl(image.id)
    }, PREVIEW_DEBOUNCE)
    return () => clearTimeout(timer)
  }, [annotations, classes, config, image])

  if (!image) return <div className="training-preview-empty">Select a dataset image to preview augmentation.</div>
  return <><div className="preview-grid"><div className="preview-pane"><span>ORIGINAL</span><div><canvas ref={originalRef} /></div></div><div className="preview-pane"><span>AUGMENTED</span><div><canvas ref={augmentedRef} /></div></div></div>{error && <div className="training-inline-error">{error}</div>}</>
}
