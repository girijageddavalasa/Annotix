import { useCallback, useEffect, useRef, useState } from 'react'

import { cancelTraining, fetchTrainingStatus, startTraining, trainingEventsUrl } from '../api/client'

const activeStates = new Set(['PREPARING', 'TRAINING'])

export function useTraining(projectId) {
  const [status, setStatus] = useState({ job: null, any_training_active: false, current_project_locked: false })
  const [logs, setLogs] = useState([])
  const [error, setError] = useState('')
  const sourceRef = useRef(null)
  const eventIdsRef = useRef(new Set())

  const refresh = useCallback(async () => {
    try { const result = await fetchTrainingStatus(); setStatus(result); setError(''); return result }
    catch (requestError) { setError(requestError.message || 'Could not load training status'); return null }
  }, [])

  useEffect(() => {
    let active = true
    eventIdsRef.current.clear()
    fetchTrainingStatus().then((result) => { if (active) { setStatus(result); setLogs([]); setError('') } }).catch((requestError) => { if (active) setError(requestError.message || 'Could not load training status') })
    return () => { active = false }
  }, [projectId])
  useEffect(() => {
    const timer = window.setInterval(refresh, 2000)
    return () => window.clearInterval(timer)
  }, [refresh])
  useEffect(() => {
    sourceRef.current?.close()
    const jobId = status.job?.id
    if (!jobId) return undefined
    const source = new EventSource(trainingEventsUrl(jobId))
    sourceRef.current = source
    const receiveLog = (event) => { const entry = JSON.parse(event.data); const eventId = entry.id || event.lastEventId || `${jobId}:${entry.type}:${entry.timestamp}:${entry.message}`; if (eventIdsRef.current.has(eventId)) return null; eventIdsRef.current.add(eventId); setLogs((current) => [...current, { ...entry, id: eventId }].slice(-1000)); return entry }
    source.addEventListener('log', receiveLog)
    source.addEventListener('metrics', (event) => { const entry = receiveLog(event); if (entry) setStatus((current) => ({ ...current, job: current.job ? { ...current.job, metrics: entry.data } : null })) })
    source.addEventListener('status', (event) => { const payload = JSON.parse(event.data); setStatus((current) => ({ ...current, job: payload.job, current_project_locked: false, any_training_active: false })); source.close() })
    source.onerror = () => refresh()
    return () => source.close()
  }, [refresh, status.job?.id])

  const start = async (configuration) => {
    setError(''); setLogs([]); eventIdsRef.current.clear()
    try { const job = await startTraining(configuration); setStatus((current) => ({ ...current, job, any_training_active: true, current_project_locked: true })); return true }
    catch (requestError) { setError(requestError.message || 'Training could not be started'); return false }
  }
  const cancel = async () => {
    if (!status.job) return
    try { await cancelTraining(status.job.id); setError('') }
    catch (requestError) { setError(requestError.message || 'Training could not be cancelled') }
  }

  return { ...status, logs, error, running: Boolean(status.job && activeStates.has(status.job.state)), refresh, start, cancel }
}
