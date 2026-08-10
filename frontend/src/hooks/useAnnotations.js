import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchAnnotations, saveAnnotations } from '../api/client'

const AUTO_SAVE_DELAY = 750

export function useAnnotations(imageId, onSaved) {
  const [annotations, setAnnotations] = useState([])
  const [loadedImageId, setLoadedImageId] = useState(null)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState('')
  const [saveStatus, setSaveStatus] = useState('saved')
  const annotationsRef = useRef([])
  const imageIdRef = useRef(imageId)
  const onSavedRef = useRef(onSaved)
  const versionRef = useRef(0)
  const persistedVersionRef = useRef(0)
  const timerRef = useRef(null)
  const inFlightRef = useRef(null)
  const saveLatestRef = useRef(null)

  const saveLatest = useCallback(async () => {
    if (!imageIdRef.current) return false
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null }
    if (inFlightRef.current) {
      await inFlightRef.current
      if (versionRef.current <= persistedVersionRef.current) return true
      return saveLatestRef.current()
    }

    const targetImageId = imageIdRef.current
    const targetVersion = versionRef.current
    const snapshot = annotationsRef.current.map((annotation) => ({ ...annotation }))
    const payload = snapshot.map(({ id, class_id, x1, y1, x2, y2 }) => ({
      id: id?.startsWith('draft-') ? null : id,
      class_id, x1, y1, x2, y2,
    }))

    setSaving(true)
    setSaveStatus('saving')
    setError('')
    const request = saveAnnotations(targetImageId, payload)
    inFlightRef.current = request
    let succeeded = false
    try {
      const result = await request
      succeeded = true
      persistedVersionRef.current = Math.max(persistedVersionRef.current, targetVersion)
      if (imageIdRef.current === targetImageId) {
        const assignedIds = new Map()
        snapshot.forEach((annotation, index) => {
          if (annotation.id?.startsWith('draft-') && result.annotations[index]) assignedIds.set(annotation.id, result.annotations[index].id)
        })
        const reconciled = annotationsRef.current.map((annotation) => assignedIds.has(annotation.id) ? { ...annotation, id: assignedIds.get(annotation.id) } : annotation)
        annotationsRef.current = reconciled
        setAnnotations(reconciled)
        const fullySaved = versionRef.current <= persistedVersionRef.current
        setDirty(!fullySaved)
        setSaveStatus(fullySaved ? 'saved' : 'unsaved')
      }
      await onSavedRef.current?.()
    } catch (requestError) {
      if (imageIdRef.current === targetImageId) {
        setDirty(true)
        setSaveStatus('failed')
        setError(requestError.message || 'Annotations could not be saved')
      }
    } finally {
      if (inFlightRef.current === request) inFlightRef.current = null
      setSaving(false)
    }

    if (succeeded && imageIdRef.current === targetImageId && versionRef.current > persistedVersionRef.current) {
      return saveLatestRef.current()
    }
    return succeeded
  }, [])
  useEffect(() => { onSavedRef.current = onSaved }, [onSaved])
  useEffect(() => { imageIdRef.current = imageId }, [imageId])
  useEffect(() => { saveLatestRef.current = saveLatest }, [saveLatest])

  const scheduleAutoSave = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      timerRef.current = null
      saveLatestRef.current()
    }, AUTO_SAVE_DELAY)
  }, [])

  const reload = useCallback(async () => {
    if (!imageIdRef.current) return
    const result = await fetchAnnotations(imageIdRef.current)
    annotationsRef.current = result.annotations
    setAnnotations(result.annotations)
    setDirty(false)
    setError('')
    setSaveStatus('saved')
    setLoadedImageId(imageIdRef.current)
    await onSavedRef.current?.()
  }, [])

  useEffect(() => {
    if (!imageId) return
    let active = true
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null }
    versionRef.current = 0
    persistedVersionRef.current = 0
    fetchAnnotations(imageId)
      .then((result) => {
        if (!active) return
        annotationsRef.current = result.annotations
        setAnnotations(result.annotations)
        setDirty(false)
        setError('')
        setSaveStatus('saved')
        setLoadedImageId(imageId)
      })
      .catch((requestError) => {
        if (!active) return
        setError(requestError.message || 'Could not load annotations')
        setSaveStatus('failed')
      })
    return () => {
      active = false
      if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null }
    }
  }, [imageId])

  const previewDraft = useCallback((next) => {
    const value = typeof next === 'function' ? next(annotationsRef.current) : next
    annotationsRef.current = value
    setAnnotations(value)
  }, [])

  const updateDraft = useCallback((next) => {
    const value = typeof next === 'function' ? next(annotationsRef.current) : next
    annotationsRef.current = value
    setAnnotations(value)
    versionRef.current += 1
    setDirty(true)
    setSaveStatus('unsaved')
    setError('')
    scheduleAutoSave()
  }, [scheduleAutoSave])

  return {
    annotations,
    updateDraft,
    previewDraft,
    loading: loadedImageId !== imageId,
    saving,
    dirty,
    error,
    saveStatus,
    save: saveLatest,
    flush: saveLatest,
    retry: saveLatest,
    reload,
  }
}
