import { useCallback, useEffect, useState } from 'react'

import { createClass, deleteClass, fetchClasses, updateClass } from '../api/client'

export function useClasses(onChanged) {
  const [classes, setClasses] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = useCallback(async () => {
    try {
      setClasses(await fetchClasses())
    } catch (requestError) {
      setError(requestError.message || 'Could not load classes')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    fetchClasses()
      .then((records) => { if (active) setClasses(records) })
      .catch((requestError) => { if (active) setError(requestError.message || 'Could not load classes') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const runMutation = useCallback(async (action, message) => {
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await action()
      await load()
      await onChanged?.()
      setSuccess(message)
      return true
    } catch (requestError) {
      setError(requestError.message || 'The class could not be saved')
      return false
    } finally {
      setSaving(false)
    }
  }, [load, onChanged])

  return {
    classes,
    loading,
    saving,
    error,
    success,
    clearFeedback: () => { setError(''); setSuccess('') },
    refresh: load,
    add: (data) => runMutation(() => createClass(data), `Class “${data.name.trim()}” created.`),
    edit: (id, data) => runMutation(() => updateClass(id, data), 'Class updated.'),
    remove: (record) => runMutation(() => deleteClass(record.id), `Class “${record.name}” deleted.`),
  }
}
