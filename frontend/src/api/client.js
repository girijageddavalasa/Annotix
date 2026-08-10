const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'

async function request(path, options) {
  const response = await fetch(`${API_BASE_URL}${path}`, options)
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const payload = await response.json()
      message = payload.detail || message
    } catch {
      // Keep the HTTP fallback when the server does not return JSON.
    }
    throw new Error(message)
  }
  return response.json()
}

export function fetchDataset() {
  return request('/dataset')
}

export function fetchDatasetImages() {
  return request('/dataset/images')
}

export function uploadDatasetZip(file, signal) {
  const body = new FormData()
  body.append('file', file)
  return request('/dataset/upload-zip', { method: 'POST', body, signal })
}

export function uploadDatasetFolder(files, signal) {
  const body = new FormData()
  for (const file of files) {
    body.append('files', file, file.webkitRelativePath || file.name)
  }
  return request('/dataset/upload-folder', { method: 'POST', body, signal })
}

export function datasetImageUrl(imageId) {
  return `${API_BASE_URL}/dataset/images/${encodeURIComponent(imageId)}`
}

export function datasetThumbnailUrl(imageId) {
  return `${API_BASE_URL}/dataset/images/${encodeURIComponent(imageId)}/thumbnail`
}

export function fetchAnnotations(imageId) {
  return request(`/annotations/${encodeURIComponent(imageId)}`)
}

export function saveAnnotations(imageId, annotations) {
  return request(`/annotations/${encodeURIComponent(imageId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ annotations }),
  })
}

export function fetchProjects() { return request('/projects') }
export function createProject(data) { return request('/projects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }) }
export function activateProject(projectId) { return request(`/projects/${projectId}/activate`, { method: 'POST' }) }
export function renameProject(projectId, data) { return request(`/projects/${projectId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }) }
export function deleteProject(projectId) { return request(`/projects/${projectId}`, { method: 'DELETE' }) }

export function fetchClasses() {
  return request('/classes')
}

export function createClass(data) {
  return request('/classes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export function updateClass(classId, data) {
  return request(`/classes/${classId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export function deleteClass(classId) {
  return request(`/classes/${classId}`, { method: 'DELETE' })
}

export function fetchTrainingStatus() { return request('/training/status') }
export function startTraining(configuration) { return request('/training/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(configuration) }) }
export function cancelTraining(jobId) { return request(`/training/jobs/${jobId}/cancel`, { method: 'POST' }) }
export function trainingEventsUrl(jobId) { return `${API_BASE_URL}/training/jobs/${encodeURIComponent(jobId)}/events` }

export function fetchModels() { return request('/predictions/models') }
export function fetchPredictionStatus() { return request('/predictions/status') }
export function startPrediction(configuration) { return request('/predictions/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(configuration) }) }
export function cancelPrediction(jobId) { return request(`/predictions/jobs/${jobId}/cancel`, { method: 'POST' }) }
export function predictionEventsUrl(jobId) { return `${API_BASE_URL}/predictions/jobs/${encodeURIComponent(jobId)}/events` }
export function fetchImagePredictions(imageId, modelId) { return request(`/predictions/images/${encodeURIComponent(imageId)}?model_id=${encodeURIComponent(modelId)}`) }
export function editPrediction(predictionId, data) { return request(`/predictions/items/${predictionId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }) }
export function acceptPrediction(predictionId) { return request(`/predictions/items/${predictionId}/accept`, { method: 'POST' }) }
export function rejectPrediction(predictionId) { return request(`/predictions/items/${predictionId}/reject`, { method: 'POST' }) }
export function acceptPredictions(predictionIds) { return request('/predictions/accept-all', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prediction_ids: predictionIds }) }) }
