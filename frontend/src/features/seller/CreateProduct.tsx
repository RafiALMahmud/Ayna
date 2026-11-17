import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Upload, X, ArrowRight } from 'lucide-react'
import { api } from '../../shared/api'
import type { Config, Product } from '../../shared/api'

export function CreateProduct({
  config,
  onClose,
  onCreated,
}: {
  config: Config
  onClose: () => void
  onCreated: (p: Product) => void
}) {
  const [files, setFiles] = useState<File[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState<Product | null>(null)
  const nameRef = useRef<HTMLInputElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    nameRef.current?.focus()
  }, [])
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (files.length < config.min_images || files.length > config.max_images) {
      setError(`Choose ${config.min_images}–${config.max_images} product photographs.`)
      return
    }
    if (files.some((f) => f.size > config.max_image_bytes)) {
      setError('An image exceeds the size limit.')
      return
    }
    const form = new FormData(event.currentTarget)
    setBusy(true)
    setError('')
    try {
      const product =
        draft ||
        (await api<Product>('/products', {
          method: 'POST',
          body: JSON.stringify({
            name: form.get('name'),
            category: form.get('category'),
            description: form.get('description'),
          }),
        }))
      setDraft(product)
      const upload = new FormData()
      files.forEach((file) => upload.append('files', file))
      const result = await api<Product>(`/products/${product.id}/images`, {
        method: 'POST',
        body: upload,
      })
      onCreated(result)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div
      className="modal-backdrop"
      onKeyDown={(event) => {
        if (event.key === 'Escape' && !busy) onClose()
        if (event.key === 'Tab') {
          const items = dialogRef.current?.querySelectorAll<HTMLElement>(
            'button:not(:disabled),input,select,textarea',
          )
          if (!items?.length) return
          const first = items[0],
            last = items[items.length - 1]
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault()
            last.focus()
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault()
            first.focus()
          }
        }
      }}
    >
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-title"
        ref={dialogRef}
      >
        <div className="section-heading">
          <div>
            <p className="eyebrow">START WITH THE REAL THING</p>
            <h2 id="create-title">Add a product</h2>
          </div>
          <button
            className="icon-button"
            aria-label="Close dialog"
            disabled={busy}
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        <form onSubmit={submit}>
          <label>
            Product name
            <input
              ref={nameRef}
              name="name"
              required
              maxLength={160}
              placeholder="e.g. Everyday leather tote"
              disabled={!!draft}
            />
          </label>
          <label>
            Category
            <select name="category" disabled={!!draft}>
              <option value="bags">Bags</option>
              <option value="shoes">Shoes</option>
              <option value="shirts">Shirts · experimental</option>
              <option value="dresses">Dresses · experimental</option>
              <option value="pants">Pants · experimental</option>
            </select>
          </label>
          <label>
            Description
            <textarea
              name="description"
              rows={2}
              maxLength={3000}
              placeholder="Materials, details, and what makes it yours."
              disabled={!!draft}
            />
          </label>
          <label className="upload-zone">
            <Upload size={24} />
            <strong>Choose product photographs</strong>
            <span>
              {config.min_images}–{config.max_images} views · JPEG, PNG, WebP ·{' '}
              {Math.round(config.max_image_bytes / 1048576)} MB each
            </span>
            <input
              aria-label="Product photographs"
              type="file"
              multiple
              accept="image/png,image/jpeg,image/webp"
              onChange={(e) => setFiles(Array.from(e.target.files || []))}
            />
          </label>
          {files.length > 0 && <p className="file-list">{files.map((f) => f.name).join(' · ')}</p>}
          <p className="muted small">
            Put the front view first. Original photographs stay private; published galleries use
            clean derivatives.
          </p>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <button className="button primary full" disabled={busy}>
            {busy ? 'Saving product…' : draft ? 'Retry photo upload' : 'Create product'}
            <ArrowRight size={17} />
          </button>
        </form>
      </div>
    </div>
  )
}
