import { useEffect, useState } from 'react'

import { activateProject, createProject, deleteProject, fetchProjects, renameProject } from '../api/client'

export function useProjects() {
  const [projects, setProjects] = useState([])
  const [currentProjectId, setCurrentProjectId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    try {
      const result = await fetchProjects()
      setProjects(result.projects)
      setCurrentProjectId(result.current_project_id)
      setError('')
      return true
    } catch (requestError) {
      setError(requestError.message || 'Could not load projects')
      return false
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let active = true
    fetchProjects().then((result) => {
      if (!active) return
      setProjects(result.projects)
      setCurrentProjectId(result.current_project_id)
    }).catch((requestError) => { if (active) setError(requestError.message || 'Could not load projects') }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const mutate = async (operation) => {
    setError('')
    try {
      await operation()
      return await load()
    } catch (requestError) {
      setError(requestError.message || 'Project operation failed')
      return false
    }
  }

  return {
    projects,
    currentProject: projects.find((project) => project.id === currentProjectId) || null,
    currentProjectId,
    loading,
    error,
    clearError: () => setError(''),
    refresh: load,
    activate: (id) => mutate(() => activateProject(id)),
    create: (name) => mutate(() => createProject({ name })),
    rename: (id, name) => mutate(() => renameProject(id, { name })),
    remove: (id) => mutate(() => deleteProject(id)),
  }
}

