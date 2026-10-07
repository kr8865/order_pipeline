import { useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import { Link } from 'react-router-dom'
import { Card } from '../components/ui'
import { errorMessage, useLoadSampleMutation, useUploadFileMutation } from '../services/api'
import { resetFilters } from '../features/filters/filtersSlice'

const SOURCES = [
  { kind: 'json', title: 'Orders', ext: '.json', desc: 'Nested JSON: orders → customer + items[]' },
  { kind: 'xml', title: 'Shipments', ext: '.xml', desc: '<shipment> with order_id, delivery_days, status' },
  { kind: 'csv', title: 'Products', ext: '.csv', desc: 'ProductID, ProductName, Category' },
]

// What each file type does to the dashboard, shown after an upload.
const EFFECT = {
  json: { noun: 'order', none: 'These order IDs are already in the database, so Total Orders does not change. Use new order IDs to add orders.' },
  xml: { noun: 'shipment', none: 'Shipments never add orders: they only update delivery days and status of existing orders.' },
  csv: { noun: 'product', none: 'Products never add orders: they only update product names and categories.' },
}

function ResultBox({ kind, result, error }) {
  if (error) return <div className="result bad">✕ {errorMessage(error)}</div>
  if (!result) return null
  const loaded = Object.entries(result.loaded || {}).map(([k, v]) => `${v} ${k}`).join(', ')
  return (
    <div className={`result ${result.warning_count ? 'warn' : 'ok'}`}>
      ✓ Loaded {loaded}{result.file ? ` from ${result.file}` : ''}
      {result.new !== undefined && (
        <div>
          <strong>{result.new} new</strong> {EFFECT[kind].noun}{result.new === 1 ? '' : 's'} added,{' '}
          <strong>{result.updated}</strong> already existed and {result.updated === 1 ? 'was' : 'were'} updated.
          {result.new === 0 && <div className="muted small">{EFFECT[kind].none}</div>}
          {kind === 'xml' && result.new > 0 && <div className="muted small">{EFFECT.xml.none}</div>}
        </div>
      )}
      {result.warning_count > 0 && (
        <details>
          <summary>{result.warning_count} data-quality warning{result.warning_count > 1 ? 's' : ''}</summary>
          <ul>{result.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </details>
      )}
    </div>
  )
}

function UploadCard({ kind, title, ext, desc }) {
  const input = useRef(null)
  const [file, setFile] = useState(null)
  const [drag, setDrag] = useState(false)
  const [upload, { data, error, isLoading, reset }] = useUploadFileMutation()
  const dispatch = useDispatch()

  const pick = (f) => { if (f) { setFile(f); reset() } }
  return (
    <Card title={`${title} (${ext})`} subtitle={desc}>
      <div className={`dropzone ${drag ? 'drag' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]) }}
        onClick={() => input.current?.click()} role="button" tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && input.current?.click()}>
        <input ref={input} type="file" accept={ext} hidden onChange={(e) => pick(e.target.files[0])} />
        {file ? <span><strong>{file.name}</strong> <span className="muted small">({(file.size / 1024).toFixed(1)} KB)</span></span>
          : <span className="muted">Drop a {ext} file here or click to browse</span>}
      </div>
      <button className="btn primary full" disabled={!file || isLoading} onClick={() => upload({ kind, file }).unwrap().then(() => dispatch(resetFilters())).catch(() => {})}>
        {isLoading ? 'Uploading…' : `Ingest ${title.toLowerCase()}`}
      </button>
      <ResultBox kind={kind} result={data} error={error} />
    </Card>
  )
}

export default function DataUpload() {
  const [loadSample, { data, error, isLoading }] = useLoadSampleMutation()
  const dispatch = useDispatch()
  // New data -> clear old filters so the dashboard shows everything that was just loaded.
  const load = (dataset) => loadSample(dataset).unwrap().then(() => dispatch(resetFilters())).catch(() => {})
  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Data</h1><p className="muted">Ingest new files. Re-uploading the same IDs updates records instead of duplicating them.</p></div>
      </div>
      <Card title="Bundled datasets" subtitle="Reset the database and reload one of the bundled datasets">
        <div className="row gap-s wrap">
          <button className="btn" disabled={isLoading} onClick={() => load('sample')}>Load original sample (2 orders)</button>
          <button className="btn primary" disabled={isLoading} onClick={() => load('demo')}>Load demo dataset (300 orders)</button>
          {isLoading && <span className="muted small"><span className="spinner sm" /> Loading…</span>}
        </div>
        {error && <div className="result bad">✕ {errorMessage(error)}</div>}
        {data && (
          <div className="result ok">✓ Reloaded. <Link to="/">Open the dashboard →</Link>
            {data.results.some((r) => r.warning_count) && (
              <details><summary>Data-quality warnings</summary>
                <ul>{data.results.flatMap((r) => r.warnings).map((w, i) => <li key={i}>{w}</li>)}</ul></details>
            )}
          </div>
        )}
      </Card>
      <div className="grid-3">{SOURCES.map((s) => <UploadCard key={s.kind} {...s} />)}</div>
      <p className="muted small">Tip: upload products first so new orders get their categories immediately — though order doesn&apos;t matter, everything is joined at query time.</p>
    </div>
  )
}
