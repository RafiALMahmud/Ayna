import { useEffect, useState } from 'react'
import { Camera, ShieldCheck } from 'lucide-react'
import { api, assetUrl } from '../../shared/api'
import type { ShopProduct } from './shared'
import { Notice, useShop } from './shared'

type TryOnJob = {
  id: string
  status: 'queued' | 'processing' | 'needs_review' | 'succeeded' | 'failed' | 'deleted'
  progress: number
  diagnostics: Record<string, unknown>
  error_code: string | null
  result_url: string | null
  disclosure: string
}

export function TryOnPanel({ product }: { product: ShopProduct }) {
  const { user, config } = useShop()
  const [job, setJob] = useState<TryOnJob | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const provider = config?.tryon_provider ?? 'disabled'
  const retention = config?.tryon_retention_hours ?? 24

  useEffect(() => {
    if (!job || !['queued', 'processing'].includes(job.status)) return
    const timer = window.setInterval(() => {
      api<TryOnJob>(`/try-on/jobs/${job.id}`)
        .then(setJob)
        .catch((reason: Error) => setError(reason.message))
    }, 1500)
    return () => window.clearInterval(timer)
  }, [job])

  if (!product.try_on_eligible) return null
  if (provider === 'disabled') {
    return (
      <section className="shop-tryon" aria-labelledby="tryon-title">
        <h2 id="tryon-title">Virtual try-on</h2>
        <p>This optional feature is unavailable. Product photos and shopping still work normally.</p>
      </section>
    )
  }
  if (!user) {
    return (
      <section className="shop-tryon" aria-labelledby="tryon-title">
        <h2 id="tryon-title">Check your photo framing</h2>
        <p>Sign in to use the private try-on diagnostic.</p>
      </section>
    )
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      setJob(
        await api<TryOnJob>(`/try-on/products/${product.id}/jobs`, {
          method: 'POST',
          headers: { 'Idempotency-Key': `tryon-${crypto.randomUUID()}` },
          body: new FormData(event.currentTarget),
        }),
      )
    } catch (reason) {
      setError((reason as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!job) return
    setBusy(true)
    setError('')
    try {
      setJob(await api<TryOnJob>(`/try-on/jobs/${job.id}`, { method: 'DELETE' }))
    } catch (reason) {
      setError((reason as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="shop-tryon" aria-labelledby="tryon-title">
      <div className="shop-tryon-heading">
        <Camera size={24} />
        <div>
          <p className="shop-kicker">PRIVATE DIAGNOSTIC</p>
          <h2 id="tryon-title">Check your photo framing</h2>
        </div>
      </div>
      <p>
        This mode checks whether the image meets basic framing requirements. It does not generate a
        garment visualization, verify sizing, or predict physical fit.
      </p>
      {!job || job.status === 'deleted' ? (
        <form className="shop-form shop-tryon-form" onSubmit={submit}>
          <label>
            Your private photo
            <input name="photo" type="file" accept="image/jpeg,image/png,image/webp" required />
          </label>
          <label>
            Framing
            <select
              name="framing"
              defaultValue={product.category === 'shirts' ? 'upper_body' : 'full_body'}
            >
              {product.category === 'shirts' && <option value="upper_body">Upper body</option>}
              <option value="full_body">Full body, head to feet</option>
            </select>
          </label>
          <label className="shop-check">
            <input name="consent" value="true" type="checkbox" required />
            I consent to processing this photo for this diagnostic.
          </label>
          <label className="shop-check">
            <input name="no_training" value="true" type="checkbox" required />
            I understand the photo is not used for model training.
          </label>
          <p className="shop-small shop-muted">
            The metadata-stripped upload is private and retained for at most {retention} hours. You
            can delete it sooner.
          </p>
          <button className="shop-button" disabled={busy}>
            {busy ? 'Uploading…' : 'Run private diagnostic'}
          </button>
        </form>
      ) : (
        <div className="shop-tryon-status" aria-live="polite">
          <strong>
            {job.status === 'needs_review'
              ? 'Photo received — real try-on is not configured'
              : job.status === 'failed'
                ? 'Diagnostic could not finish'
                : job.status === 'succeeded'
                  ? 'Try-on result ready'
                  : `Processing ${job.progress}%`}
          </strong>
          <p>{job.disclosure}</p>
          {job.result_url && <img src={assetUrl(job.result_url)} alt="Private try-on result" />}
          <button className="shop-button outline" disabled={busy} onClick={remove}>
            Delete private upload
          </button>
        </div>
      )}
      <div className="shop-tryon-privacy">
        <ShieldCheck size={18} /> Never public; authenticated access only.
      </div>
      <Notice error={error} />
    </section>
  )
}
