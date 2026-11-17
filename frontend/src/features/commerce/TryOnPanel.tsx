import { useEffect, useState } from 'react'
import { Camera, Download, RotateCcw, ShieldCheck } from 'lucide-react'
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

const stageLabels: Record<string, string> = {
  input_preparation: 'Preparing private inputs',
  process_startup: 'Starting the isolated worker',
  model_loading: 'Loading local AI models',
  pose_detection: 'Detecting body pose',
  human_parsing: 'Mapping clothing and body regions',
  garment_preprocessing: 'Preparing the selected garment',
  cuda_synthesis: 'Generating the preview on the RTX GPU',
  output_parsing: 'Mapping the generated garment region',
  detail_restoration: 'Restoring garment detail',
  skin_recovery: 'Recovering exposed skin tone',
  image_encoding: 'Encoding the generated image',
  output_validation: 'Validating the private result',
}

const failureMessages: Record<string, string> = {
  TRYON_TIMEOUT:
    'Generation exceeded the 15-minute safety limit. The worker was stopped and your original upload remains private and unchanged.',
  TRYON_CANCELLED: 'Generation was cancelled safely. No partial result was published.',
  TRYON_OUTPUT_INVALID: 'The model returned an invalid image, so Ayna rejected the result.',
  TRYON_OUTPUT_MISSING: 'The model finished without a result image, so Ayna rejected the job.',
  TRYON_INFERENCE_FAILED: 'The local model stopped unexpectedly before producing a valid result.',
  TRYON_MODEL_NOT_CONFIGURED: 'The local try-on model is not configured on this machine.',
}

export function TryOnPanel({ product }: { product: ShopProduct }) {
  const { user, config } = useShop()
  const [job, setJob] = useState<TryOnJob | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [previewUrl, setPreviewUrl] = useState('')
  const [reveal, setReveal] = useState(50)
  const provider = config?.tryon_provider ?? 'disabled'
  const retention = config?.tryon_retention_hours ?? 24
  const realPreview = provider === 'fashn_vton'

  useEffect(() => {
    if (!user || !realPreview) return
    let active = true
    api<TryOnJob | null>(`/try-on/products/${product.id}/jobs/latest`)
      .then((latest) => {
        if (active && latest) setJob((current) => current ?? latest)
      })
      .catch(() => {
        /* The regular product page remains usable when recovery is unavailable. */
      })
    return () => {
      active = false
    }
  }, [product.id, realPreview, user])

  useEffect(() => {
    if (!job || !['queued', 'processing'].includes(job.status)) return
    const timer = window.setInterval(() => {
      api<TryOnJob>(`/try-on/jobs/${job.id}`)
        .then(setJob)
        .catch((reason: Error) => setError(reason.message))
    }, 1500)
    return () => window.clearInterval(timer)
  }, [job])

  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    },
    [previewUrl],
  )

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
        <h2 id="tryon-title">{realPreview ? 'Generate a clothing preview' : 'Check your photo framing'}</h2>
        <p>Sign in to use this private feature.</p>
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

  async function downloadResult() {
    if (!job?.result_url) return
    setBusy(true)
    setError('')
    try {
      const response = await fetch(assetUrl(job.result_url), { credentials: 'include' })
      if (!response.ok) throw new Error('The private result could not be downloaded')
      const temporary = URL.createObjectURL(await response.blob())
      const link = document.createElement('a')
      link.href = temporary
      link.download = `ayna-try-on-${job.id}.png`
      link.click()
      URL.revokeObjectURL(temporary)
    } catch (reason) {
      setError((reason as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const currentStage = typeof job?.diagnostics.stage === 'string' ? job.diagnostics.stage : ''
  const runtime =
    job?.diagnostics.runtime && typeof job.diagnostics.runtime === 'object'
      ? (job.diagnostics.runtime as Record<string, unknown>)
      : {}
  const synthesisDevice = runtime.synthesis_device
  const cudaDevice = typeof runtime.cuda_device === 'string' ? runtime.cuda_device : ''
  const deviceLine =
    synthesisDevice === 'cuda'
      ? `Device: ${cudaDevice || 'CUDA GPU'}`
      : synthesisDevice === 'cpu'
        ? 'Device: CPU'
        : ''
  const stageLabel =
    currentStage === 'cuda_synthesis'
      ? synthesisDevice === 'cuda'
        ? 'Generating the preview on the RTX GPU'
        : synthesisDevice === 'cpu'
          ? 'Generating the preview on the CPU'
          : 'Generating the preview'
      : stageLabels[currentStage] || 'Processing the private preview'
  const failureMessage = job?.error_code
    ? failureMessages[job.error_code] || `The worker stopped with error ${job.error_code}.`
    : ''

  return (
    <section className="shop-tryon" aria-labelledby="tryon-title">
      <div className="shop-tryon-heading">
        <Camera size={24} />
        <div>
          <p className="shop-kicker">{realPreview ? 'PRIVATE GENERATED PREVIEW' : 'PRIVATE DIAGNOSTIC'}</p>
          <h2 id="tryon-title">{realPreview ? 'See a generated clothing preview' : 'Check your photo framing'}</h2>
        </div>
      </div>
      <p>
        {realPreview
          ? 'This local model generates a synthetic appearance preview. It does not verify sizing or predict physical fit.'
          : 'This mode checks whether the image meets basic framing requirements. It does not generate a garment visualization, verify sizing, or predict physical fit.'}
      </p>
      {!job || job.status === 'deleted' ? (
        <form className="shop-form shop-tryon-form" onSubmit={submit}>
          <label>
            Your private photo
            <input
              name="photo"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              required
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (previewUrl) URL.revokeObjectURL(previewUrl)
                setPreviewUrl(file ? URL.createObjectURL(file) : '')
              }}
            />
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
            I consent to processing this photo for this {realPreview ? 'generated preview' : 'diagnostic'}.
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
            {busy ? 'Uploading…' : realPreview ? 'Generate private preview' : 'Run private diagnostic'}
          </button>
        </form>
      ) : (
        <div className="shop-tryon-status" aria-live="polite">
          <strong>
            {job.status === 'needs_review'
              ? 'Photo received — real try-on is not configured'
              : job.status === 'failed'
                ? `${realPreview ? 'Try-on' : 'Diagnostic'} could not finish`
                : job.status === 'succeeded'
                  ? 'Try-on result ready'
                  : `${stageLabel} · ${job.progress}%`}
          </strong>
          {job.status === 'failed' && <p className="shop-error">{failureMessage}</p>}
          <p>{job.disclosure}</p>
          {job.status === 'succeeded' && deviceLine && (
            <p className="shop-small shop-muted">{deviceLine}</p>
          )}
          {job.result_url && previewUrl && (
            <div
              className="shop-tryon-compare"
              style={{ '--reveal': `${reveal}%` } as React.CSSProperties}
            >
              <img src={previewUrl} alt="Original private upload" />
              <img
                className="result"
                src={assetUrl(job.result_url)}
                alt="Generated try-on result"
              />
              <span className="before">Before</span>
              <span className="after">After</span>
            </div>
          )}
          {job.result_url && !previewUrl && (
            <img src={assetUrl(job.result_url)} alt="Generated try-on result" />
          )}
          {job.result_url && previewUrl && (
            <label className="shop-tryon-slider">
              Compare before and after
              <input
                aria-label="Compare before and after"
                type="range"
                min="0"
                max="100"
                value={reveal}
                onChange={(event) => setReveal(Number(event.target.value))}
              />
            </label>
          )}
          <div className="shop-tryon-actions">
            {job.result_url && (
              <button
                className="shop-button"
                disabled={busy}
                onClick={() => void downloadResult()}
              >
                <Download size={16} /> Download result
              </button>
            )}
            {!['queued', 'processing'].includes(job.status) && (
              <button className="shop-button outline" disabled={busy} onClick={() => setJob(null)}>
                <RotateCcw size={16} /> Try another photo
              </button>
            )}
          </div>
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
