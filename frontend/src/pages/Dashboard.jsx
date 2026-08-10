import { ArrowRight, Boxes, Database, Layers3, ShieldCheck } from 'lucide-react'

import { StatCard } from '../components/ui/StatCard'

export function Dashboard({ stats, onOpenDataset }) {
  return (
    <div className="dashboard">
      <div className="page-heading">
        <div>
          <span className="eyebrow">PROJECT OVERVIEW</span>
          <h1>Welcome to Annotix</h1>
          <p>Your private, local workspace for building computer vision datasets.</p>
        </div>
        <span className="privacy-note"><ShieldCheck size={16} /> Data stays on this machine</span>
      </div>

      <section className="stats-grid" aria-label="Project statistics">
        <StatCard icon={Database} label="DATASET" value={stats.total_images} detail="images loaded" accent="blue" />
        <StatCard icon={Boxes} label="ANNOTATIONS" value={stats.total_objects} detail="bounding boxes" accent="violet" />
        <StatCard icon={Layers3} label="CLASSES" value={stats.classes} detail="labels configured" accent="green" />
      </section>

      <section className="workspace-panel">
        <div className="workspace-panel__copy">
          <span className="step-badge">01</span>
          <h2>Start with your dataset</h2>
          <p>Create a project and add a local image collection. Annotix will keep your source files and future annotations inside this workspace.</p>
          <button className="primary-button primary-button--enabled" type="button" onClick={onOpenDataset}>
            {stats.total_images ? 'Open dataset' : 'Import a dataset'} <ArrowRight size={17} />
          </button>
        </div>
        <div className="empty-preview" aria-hidden="true">
          <div className="empty-preview__frame">
            <Database size={30} />
            <span>Local image workspace</span>
          </div>
          <span className="corner corner--tl" />
          <span className="corner corner--tr" />
          <span className="corner corner--bl" />
          <span className="corner corner--br" />
        </div>
      </section>

      <section className="activity-panel">
        <div><h2>Recent activity</h2><p>Project events will appear here.</p></div>
        <div className="activity-empty"><span className="activity-empty__line" /> No activity yet</div>
      </section>
    </div>
  )
}
