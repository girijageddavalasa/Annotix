import { Activity, Terminal } from 'lucide-react'

const STATUS_LABELS = {
  IDLE: 'READY',
  PREPARING: 'PREPARING',
  TRAINING: 'TRAINING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  CANCELLED: 'CANCELLED',
}

export function TrainingConsole({ projectName, stats, device, state = 'IDLE', logs = [], metrics, onCancel }) {
  const timestamp = new Date().toLocaleTimeString('en-GB', { hour12: false })
  const initialLogs = [
    `Annotix training console initialized.`,
    `Active project: ${projectName || 'No active project'}`,
    `Found ${stats.annotated_images} annotated images.`,
    `Found ${stats.classes} classes.`,
    `Model: YOLO`,
    `Device: ${device === 'auto' ? 'Auto' : device.toUpperCase()}`,
    `Waiting to start training...`,
  ]
  const displayedLogs = logs.length ? logs : initialLogs.map((message) => ({ timestamp, level: 'INFO', message }))

  return <section className="training-console-section">
    <div className="training-console">
      <header><div><Terminal size={16} /><span>TRAINING CONSOLE</span></div><div className="console-actions">{onCancel && <button type="button" onClick={onCancel}>Cancel training</button>}<strong className={`console-state console-state--${state.toLowerCase()}`}><i /> {STATUS_LABELS[state] || state}</strong></div></header>
      <div className="console-output" role="log" aria-live="polite">
        {displayedLogs.map((entry, index) => <div className={`console-line console-line--${(entry.level || 'INFO').toLowerCase()}`} key={`${entry.timestamp}-${index}`}><time>[{entry.timestamp || timestamp}]</time><b>{entry.level || 'INFO'}</b><span>{entry.message}</span></div>)}
      </div>
    </div>
    <aside className="training-metrics"><header><Activity size={16} /><span>TRAINING METRICS</span></header><dl>{[['Epoch', metrics?.epoch ? `${metrics.epoch} / ${metrics.total_epochs}` : '--'], ['Loss', metrics?.loss ?? '--'], ['Box loss', metrics?.box_loss ?? '--'], ['Class loss', metrics?.class_loss ?? '--'], ['mAP50', metrics?.map50 ?? '--'], ['mAP50-95', metrics?.map50_95 ?? '--']].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{typeof value === 'number' ? value.toFixed(4) : value}</dd></div>)}</dl><div className="metrics-progress"><span><b>Progress</b><strong>{Math.round(metrics?.progress || 0)}%</strong></span><div><i style={{ width: `${metrics?.progress || 0}%` }} /></div><small>{metrics?.epoch ? `Epoch ${metrics.epoch} completed` : 'Not started'}</small></div></aside>
  </section>
}
