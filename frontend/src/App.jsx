import { useCallback, useRef, useState } from 'react'

import { AppShell } from './components/layout/AppShell'
import { Dashboard } from './pages/Dashboard'
import { Dataset } from './pages/Dataset'
import { Classes } from './pages/Classes'
import { Annotation } from './pages/Annotation'
import { Training } from './pages/Training'
import { useDataset } from './hooks/useDataset'
import { useClasses } from './hooks/useClasses'
import { useProjects } from './hooks/useProjects'
import { useTraining } from './hooks/useTraining'
import { ProjectUnsavedDialog } from './components/projects/ProjectUnsavedDialog'

export default function App() {
  const [currentPage, setCurrentPage] = useState('Overview')
  const [projectBusy, setProjectBusy] = useState(false)
  const [pendingProjectChange, setPendingProjectChange] = useState(null)
  const annotationRef = useRef(null)
  const projects = useProjects()
  const training = useTraining(projects.currentProjectId)
  const dataset = useDataset()
  const classes = useClasses(dataset.refresh)
  const refreshDataset = dataset.refresh
  const refreshClasses = classes.refresh
  const refreshProjectState = useCallback(async () => {
    await Promise.all([refreshDataset(), refreshClasses()])
  }, [refreshClasses, refreshDataset])

  const executeProjectAction = useCallback(async (action) => {
    setProjectBusy(true)
    try {
      const succeeded = await action()
      if (succeeded) await refreshProjectState()
      return succeeded
    } finally {
      setProjectBusy(false)
    }
  }, [refreshProjectState])

  const requestProjectAction = useCallback((action) => {
    if (currentPage === 'Annotation' && annotationRef.current?.dirty) {
      return new Promise((resolve) => setPendingProjectChange({ action, resolve }))
    }
    return executeProjectAction(action)
  }, [currentPage, executeProjectAction])

  const finishPending = async (saveFirst) => {
    if (saveFirst && !(await annotationRef.current?.save())) return
    const succeeded = await executeProjectAction(pendingProjectChange.action)
    pendingProjectChange.resolve(succeeded)
    setPendingProjectChange(null)
  }

  const cancelPending = () => {
    pendingProjectChange.resolve(false)
    setPendingProjectChange(null)
  }

  const projectActions = {
    onActivate: (id) => requestProjectAction(() => projects.activate(id)),
    onCreate: (name) => requestProjectAction(() => projects.create(name)),
    onRename: (id, name) => requestProjectAction(() => projects.rename(id, name)),
    onDelete: (id) => requestProjectAction(() => projects.remove(id)),
  }

  return (
    <AppShell currentPage={currentPage} onNavigate={setCurrentPage} stats={dataset.stats} projectState={projects} projectBusy={projectBusy} projectActions={projectActions} projectLocked={training.current_project_locked}>
      {currentPage === 'Dataset' ? (
        <Dataset dataset={dataset} locked={training.current_project_locked} />
      ) : currentPage === 'Classes' ? (
        <Classes classState={classes} locked={training.current_project_locked} />
      ) : currentPage === 'Annotation' ? (
        <Annotation ref={annotationRef} dataset={dataset} classState={classes} onNavigate={setCurrentPage} onSaved={refreshProjectState} locked={training.current_project_locked} projectId={projects.currentProjectId} />
      ) : currentPage === 'Training' ? (
        <Training dataset={dataset} classes={classes.classes} projectName={projects.currentProject?.name} training={training} />
      ) : (
        <Dashboard stats={dataset.stats} onOpenDataset={() => setCurrentPage('Dataset')} />
      )}
      {pendingProjectChange && <ProjectUnsavedDialog busy={projectBusy} onCancel={cancelPending} onDiscard={() => finishPending(false)} onSave={() => finishPending(true)} />}
    </AppShell>
  )
}
