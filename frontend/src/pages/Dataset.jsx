import { useMemo, useRef, useState } from 'react'
import { Archive, CheckCircle2, FileArchive, FolderOpen, Image, Search, TriangleAlert, UploadCloud, X } from 'lucide-react'

import { datasetImageUrl } from '../api/client'
import { StatCard } from '../components/ui/StatCard'

const filters = ['All', 'Annotated', 'Unannotated']

export function Dataset({ dataset, locked = false }) {
  const { stats, images, loading, importing, error, result, runImport, cancelImport } = dataset
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('All')
  const zipInput = useRef(null)
  const folderInput = useRef(null)

  const filteredImages = useMemo(() => images.filter((image) => {
    const matchesSearch = image.filename.toLowerCase().includes(search.trim().toLowerCase())
    const matchesFilter = filter === 'All' || image.annotation_status === filter.toLowerCase()
    return matchesSearch && matchesFilter
  }), [filter, images, search])

  const handleZip = (event) => {
    const file = event.target.files?.[0]
    if (file) runImport('zip', file)
    event.target.value = ''
  }

  const handleFolder = (event) => {
    const files = Array.from(event.target.files || [])
    if (files.length) runImport('folder', files)
    event.target.value = ''
  }

  return (
    <div className="dashboard dataset-page">
      <div className="page-heading dataset-heading">
        <div>
          <span className="eyebrow">LOCAL DATASET</span>
          <h1>Dataset</h1>
          <p>Import images into your local Annotix workspace.</p>
        </div>
        <span className="privacy-note"><CheckCircle2 size={16} /> Persisted locally</span>
      </div>

      <section className="stats-grid stats-grid--four" aria-label="Dataset statistics">
        <StatCard icon={Image} label="TOTAL IMAGES" value={stats.total_images} detail="images indexed" accent="blue" />
        <StatCard icon={CheckCircle2} label="ANNOTATED" value={stats.annotated_images} detail={`${stats.total_objects} total objects`} accent="green" />
        <StatCard icon={Archive} label="UNANNOTATED" value={stats.unannotated_images} detail="images remaining" accent="violet" />
        <StatCard icon={UploadCloud} label="CLASSES" value={stats.classes} detail="labels configured" accent="amber" />
      </section>

      <section className="import-card">
        <div className="import-card__heading">
          <div>
            <span className="eyebrow">IMPORT</span>
            <h2>{stats.total_images ? 'Add more images' : 'Import your image dataset'}</h2>
            <p>Choose a ZIP archive or select an image folder. Nested folders are preserved.</p>
          </div>
          <span className="supported-types">JPG · PNG · WEBP · BMP</span>
        </div>

        <div className="import-options">
          <button className="import-option" type="button" onClick={() => zipInput.current?.click()} disabled={importing || locked}>
            <span className="import-option__icon"><FileArchive size={25} /></span>
            <span><strong>Upload ZIP</strong><small>Select an archive containing images</small></span>
          </button>
          <span className="import-divider">OR</span>
          <button className="import-option" type="button" onClick={() => folderInput.current?.click()} disabled={importing || locked}>
            <span className="import-option__icon import-option__icon--folder"><FolderOpen size={25} /></span>
            <span><strong>Select Image Folder</strong><small>Import a folder and its subfolders</small></span>
          </button>
          <input ref={zipInput} className="visually-hidden" type="file" accept=".zip,application/zip" onChange={handleZip} />
          <input ref={folderInput} className="visually-hidden" type="file" webkitdirectory="" directory="" multiple onChange={handleFolder} />
        </div>

        {locked && <div className="feedback feedback--warning"><TriangleAlert size={17} /><span>Dataset imports are paused while this project is training.</span></div>}
        {importing && (
          <div className="import-progress">
            <span className="spinner" />
            <div><strong>Importing dataset...</strong><small>Images are being copied and indexed locally.</small></div>
            <button type="button" onClick={cancelImport}><X size={15} /> Cancel</button>
          </div>
        )}
        {error && <div className="feedback feedback--error"><TriangleAlert size={17} /><span>{error}</span></div>}
        {result && (
          <div className="feedback-wrap">
            <div className="feedback feedback--success"><CheckCircle2 size={17} /><span>{result.imported_count} images imported successfully.</span></div>
            {result.issues.length > 0 && (
              <details className="import-issues">
                <summary>{result.issues.length} file{result.issues.length === 1 ? '' : 's'} skipped</summary>
                <ul>{result.issues.map((issue, index) => <li key={`${issue.filename}-${index}`}><span>{issue.filename}</span>{issue.reason}</li>)}</ul>
              </details>
            )}
          </div>
        )}
      </section>

      <section className="gallery-section">
        <div className="gallery-toolbar">
          <div><h2>Images</h2><span>{filteredImages.length} of {images.length}</span></div>
          <div className="gallery-controls">
            <label className="search-field"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search filename" /></label>
            <div className="filter-group">
              {filters.map((item) => <button className={filter === item ? 'active' : ''} type="button" key={item} onClick={() => setFilter(item)}>{item}</button>)}
            </div>
          </div>
        </div>

        {loading ? (
          <div className="gallery-empty"><span className="spinner" /> Loading dataset...</div>
        ) : filteredImages.length > 0 ? (
          <div className="image-grid">
            {filteredImages.map((image) => (
              <article className="image-card" key={image.id}>
                <div className="image-card__preview"><img src={datasetImageUrl(image.id)} alt={image.filename} loading="lazy" /></div>
                <div className="image-card__meta"><strong title={image.relative_path}>{image.filename}</strong><span className={`status-pill status-pill--${image.annotation_status}`}>{image.annotation_status}</span></div>
              </article>
            ))}
          </div>
        ) : (
          <div className="gallery-empty">
            <span className="gallery-empty__icon"><Image size={27} /></span>
            <strong>{images.length ? 'No images match your filters' : 'No images imported yet'}</strong>
            <p>{images.length ? 'Try a different filename or annotation status.' : 'Use one of the import options above to build your dataset.'}</p>
          </div>
        )}
      </section>
    </div>
  )
}
