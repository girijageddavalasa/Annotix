import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchDataset, fetchDatasetImages, uploadDatasetFolder, uploadDatasetZip } from '../api/client'

const emptyStats = { total_images: 0, annotated_images: 0, unannotated_images: 0, classes: 0, total_objects: 0 }

export function useDataset() {
  const [stats, setStats] = useState(emptyStats)
  const [images, setImages] = useState([])
  const [loading, setLoading] = useState(true)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const abortController = useRef(null)

  const refresh = useCallback(async () => {
    try {
      const [state, imageList] = await Promise.all([fetchDataset(), fetchDatasetImages()])
      setStats(state.stats)
      setImages(imageList)
    } catch (requestError) {
      setError(requestError.message || 'Could not load the dataset')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    Promise.all([fetchDataset(), fetchDatasetImages()])
      .then(([state, imageList]) => {
        if (!active) return
        setStats(state.stats)
        setImages(imageList)
      })
      .catch((requestError) => {
        if (active) setError(requestError.message || 'Could not load the dataset')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [])

  const runImport = useCallback(async (kind, selection) => {
    abortController.current = new AbortController()
    setImporting(true)
    setError('')
    setResult(null)
    try {
      const importResult = kind === 'zip'
        ? await uploadDatasetZip(selection, abortController.current.signal)
        : await uploadDatasetFolder(selection, abortController.current.signal)
      setResult(importResult)
      await refresh()
    } catch (requestError) {
      if (requestError.name !== 'AbortError') {
        setError(requestError.message || 'Dataset import failed')
      }
    } finally {
      setImporting(false)
      abortController.current = null
    }
  }, [refresh])

  const cancelImport = useCallback(() => abortController.current?.abort(), [])

  return { stats, images, loading, importing, error, result, refresh, runImport, cancelImport }
}
