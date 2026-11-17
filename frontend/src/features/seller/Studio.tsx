import { Suspense, useCallback, useEffect, useState } from 'react'
import { Plus, ArrowRight, Box, Images, Sparkles, CheckCheck, RefreshCw } from 'lucide-react'
import { api, assetUrl } from '../../shared/api'
import type { Config, Job, Product, Quality } from '../../shared/api'
import { CreateProduct } from './CreateProduct'
import { ReviewPanel } from '../review/ReviewPanel'
import { LazyModelViewer as ModelViewer } from '../../shared/LazyModelViewer'

const label = (value: string) => value.replaceAll('_', ' ')

export function Studio({ config }: { config: Config }) {
  const [products, setProducts] = useState<Product[]>([])
  const [selected, setSelected] = useState<Product | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [quality, setQuality] = useState<Quality | null>(null)
  const [creating, setCreating] = useState(false)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const refresh = useCallback(async () => {
    const result = await api<Product[]>('/products')
    setProducts(result)
    setSelected((previous) =>
      previous ? result.find((p) => p.id === previous.id) || null : result[0] || null,
    )
  }, [])
  useEffect(() => {
    refresh()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [refresh])
  const selectedId = selected?.id
  useEffect(() => {
    let active = true
    setJob(null)
    setQuality(null)
    if (selectedId)
      api<Job[]>(`/products/${selectedId}/generation-jobs`)
        .then((jobs) => {
          if (active) setJob(jobs[0] || null)
        })
        .catch((e) => {
          if (active) setError(e.message)
        })
    return () => {
      active = false
    }
  }, [selectedId])
  const jobId = job?.id,
    jobStatus = job?.status
  useEffect(() => {
    if (!selectedId || !jobId) return
    let active = true
    if (jobStatus === 'succeeded') {
      api<Quality>(`/products/${selectedId}/quality`)
        .then((result) => {
          if (active) setQuality(result)
        })
        .catch((e) => {
          if (active) setError(e.message)
        })
      return () => {
        active = false
      }
    }
    if (jobStatus !== 'queued' && jobStatus !== 'processing') return
    let inFlight = false
    const timer = setInterval(async () => {
      if (inFlight) return
      inFlight = true
      try {
        const result = await api<Job>(`/generation-jobs/${jobId}`)
        if (!active) return
        setJob(result)
        if (result.status === 'succeeded' || result.status === 'failed') await refresh()
      } catch (err) {
        if (active) setError((err as Error).message)
      } finally {
        inFlight = false
      }
    }, 1000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [selectedId, jobId, jobStatus, refresh])
  async function generate() {
    if (!selected) return
    setBusy(true)
    setError('')
    try {
      setJob(
        await api<Job>(`/products/${selected.id}/generation-jobs`, {
          method: 'POST',
          headers: { 'Idempotency-Key': crypto.randomUUID() },
        }),
      )
      await refresh()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }
  async function cancelGeneration() {
    if (!job) return
    setBusy(true)
    setError('')
    try {
      setJob(await api<Job>(`/generation-jobs/${job.id}`, { method: 'DELETE' }))
      await refresh()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }
  function updated(product: Product) {
    setSelected(product)
    setProducts((all) => all.map((p) => (p.id === product.id ? product : p)))
  }
  async function labelView(id: string, view: string) {
    if (!selected) return
    const images = selected.images.map((image) => ({
      id: image.id,
      view_tag:
        image.id === id
          ? view
          : view === 'front' && image.view_tag === 'front'
            ? 'unspecified'
            : image.view_tag,
    }))
    images.sort((a, b) => Number(b.view_tag === 'front') - Number(a.view_tag === 'front'))
    setBusy(true)
    setError('')
    try {
      updated(
        await api<Product>(`/products/${selected.id}/images/order`, {
          method: 'PUT',
          body: JSON.stringify({ images }),
        }),
      )
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">YOUR PRODUCTS. A NEW DIMENSION.</p>
          <h1>
            Product studio<span>.</span>
          </h1>
          <p className="muted">From your photographs to a more immersive product experience.</p>
        </div>
        <button
          className="button primary"
          onClick={() => setCreating(true)}
          disabled={!config.dev_auth_enabled && !config.seller_authenticated}
        >
          <Plus size={17} /> Add product
        </button>
      </div>
      <section className="intro-banner">
        <div>
          <span className="tag light">MEET YOUR NEXT PERSPECTIVE</span>
          <h2>
            Good products deserve
            <br />a closer look.
          </h2>
          <p>
            Upload your photographs. Explore a 3D preview.
            <br />
            Review every detail before it goes live.
          </p>
        </div>
        <div className="process">
          <span>
            <Images size={20} /> Photograph
          </span>
          <ArrowRight size={16} />
          <span>
            <Sparkles size={20} /> Generate
          </span>
          <ArrowRight size={16} />
          <span>
            <CheckCheck size={20} /> Review
          </span>
        </div>
        <div className="banner-decoration" aria-hidden="true">
          a
        </div>
      </section>
      <div className="stats">
        <div>
          <span className="stat-icon">
            <Box size={19} />
          </span>
          <strong>{products.length}</strong>
          <span>Total products</span>
        </div>
        <div>
          <span className="stat-icon peach">
            <RefreshCw size={18} />
          </span>
          <strong>{products.filter((p) => p.publish_status === 'needs_review').length}</strong>
          <span>Awaiting review</span>
        </div>
        <div>
          <span className="stat-icon green">
            <CheckCheck size={19} />
          </span>
          <strong>{products.filter((p) => p.publish_status === 'approved').length}</strong>
          <span>Published previews</span>
        </div>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
          <button
            className="text-button"
            onClick={() => {
              setError('')
              refresh().catch((e) => setError(e.message))
            }}
          >
            Retry
          </button>
        </p>
      )}
      <div className="workspace">
        <section className="catalog-panel">
          <div className="section-heading">
            <h2>
              Your products <span className="count">{products.length}</span>
            </h2>
            <button
              className="icon-button"
              aria-label="Refresh products"
              onClick={() => refresh().catch((e) => setError(e.message))}
            >
              <RefreshCw size={16} />
            </button>
          </div>
          <p className="muted small">A place for everything you're making.</p>
          {loading ? (
            <p className="muted">Loading products…</p>
          ) : products.length ? (
            <div className="product-list">
              {products.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setSelected(p)}
                  className={`product-row ${selected?.id === p.id ? 'selected' : ''}`}
                >
                  <div className="product-thumb">
                    {p.images[0] ? (
                      <img src={assetUrl(p.images[0].url)} alt="" />
                    ) : (
                      <Box size={24} />
                    )}
                  </div>
                  <div>
                    <strong>{p.name}</strong>
                    <span className="muted small">
                      {p.category} · {p.images.length} photos
                    </span>
                    <span className={`status ${p.publish_status}`}>{label(p.publish_status)}</span>
                  </div>
                  <ArrowRight size={16} />
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-products">
              <div className="empty-icon">
                <Plus size={26} strokeWidth={1.5} />
              </div>
              <h3>Start with something yours.</h3>
              <p className="muted small">
                Add a product and 2–5 photographs
                <br />
                to bring your studio to life.
              </p>
              <button className="text-button" onClick={() => setCreating(true)}>
                Add your first product <ArrowRight size={15} />
              </button>
            </div>
          )}
          <div className="catalog-note">
            <span>01 — A LITTLE GUIDANCE</span>
            <p>
              Different angles tell a fuller story. Start with a clear front view, then add the
              sides and details.
            </p>
          </div>
        </section>
        <section className="preview-panel">
          <div className="section-heading">
            <h2>{selected?.name || 'Room for a new perspective'}</h2>
            <span className="tag">3D PREVIEW</span>
          </div>
          <Suspense fallback={<div className="viewer-fallback">Preparing your studio…</div>}>
            <ModelViewer
              mock={job?.provider === 'mock'}
              url={job?.model_asset_url ? assetUrl(job.model_asset_url) : null}
              photo={selected?.images[0] ? assetUrl(selected.images[0].url) : undefined}
            />
          </Suspense>
          <div className="preview-caption">
            <p>
              <span className="status-dot" />
              {job ? `Generation ${job.status} · ${job.progress}%` : 'Ready when you are'}
            </p>
            <span className="muted small">
              {(job?.provider || config.provider) === 'mock'
                ? 'Mock provider · No credits used'
                : (job?.provider || config.provider) === 'local_triposr'
                  ? 'Local TripoSR · Front photo only · No paid API'
                : `${(job?.provider || config.provider) === 'tripo' ? 'Tripo' : 'Meshy'} · Paid provider enabled`}
            </span>
          </div>
          {job && (job.status === 'queued' || job.status === 'processing') && (
            <>
              <progress max="100" value={job.progress} aria-label="Generation progress" />
              <button className="button secondary" disabled={busy} onClick={cancelGeneration}>
                Cancel generation
              </button>
            </>
          )}
          {job?.error_code && (
            <p role="alert" className="error">
              Generation failed: {job.error_code}.
              {job.provider === 'mock'
                ? ' You can retry.'
                : ' Check the provider dashboard before retrying; a new request may cost credits.'}
            </p>
          )}
          {selected && (
            <>
              <div className="photo-strip">
                {selected.images.map((i) => (
                  <img
                    key={i.id}
                    src={assetUrl(i.url)}
                    alt={`${selected.name}, ${i.view_tag} view`}
                  />
                ))}
              </div>
              {selected.publish_status !== 'generating' && (
                <fieldset className="view-labels">
                  <legend>Photograph directions</legend>
                  <p className="small muted">
                    Changing labels revokes 3D approval. Labels describe your photos; they do not
                    verify camera alignment.
                  </p>
                  {selected.images.map((image, index) => (
                    <label key={image.id}>
                      Photo {index + 1}
                      <select
                        aria-label={`Direction for photo ${index + 1}`}
                        value={image.view_tag}
                        disabled={busy}
                        onChange={(event) => void labelView(image.id, event.target.value)}
                      >
                        {['front', 'left', 'right', 'side', 'back', 'detail', 'unspecified'].map(
                          (view) => (
                            <option key={view} value={view}>
                              {view}
                            </option>
                          ),
                        )}
                      </select>
                    </label>
                  ))}
                </fieldset>
              )}
              {selected.publish_status !== 'generating' && (
                <button
                  className="button primary"
                  disabled={busy || selected.images.length < config.min_images}
                  onClick={generate}
                >
                  <Sparkles size={16} />
                  {busy
                    ? 'Starting…'
                    : config.provider === 'mock'
                      ? 'Generate mock preview'
                      : config.provider === 'local_triposr'
                        ? 'Generate locally with TripoSR (front photo)'
                      : `Generate with ${config.provider === 'tripo' ? 'Tripo' : 'Meshy'} (uses credits)`}
                </button>
              )}
              {job?.status === 'succeeded' && selected.publish_status !== 'draft' && (
                <ReviewPanel product={selected} quality={quality} onReviewed={updated} />
              )}
              {!!job?.preview_asset_urls.length && (
                <div>
                  <h3>Model inspection renders</h3>
                  <p className="small muted">
                    These are generated views, not reference photographs or proof of accuracy.
                  </p>
                  <div className="photo-strip">
                    {job.preview_asset_urls.map((url, index) => (
                      <img
                        key={url}
                        src={assetUrl(url)}
                        alt={`Generated model inspection view ${index + 1}`}
                      />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
          <p className="disclosure">
            {job?.disclosure ||
              'AI-generated 3D preview. Mock mode uses a dummy model, not a product reconstruction. Original photos remain the source of truth.'}
          </p>
        </section>
      </div>
      {creating && (
        <CreateProduct
          config={config}
          onClose={() => setCreating(false)}
          onCreated={(p) => {
            setCreating(false)
            setSelected(p)
            setProducts((all) => [p, ...all.filter((x) => x.id !== p.id)])
          }}
        />
      )}
    </>
  )
}
