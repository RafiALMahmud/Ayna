import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { TryOnPanel } from './TryOnPanel'
import type { ShopProduct } from './shared'

const state = vi.hoisted(() => ({ api: vi.fn(), user: { id: 'buyer', name: 'Buyer' } }))
vi.mock('../../shared/api', () => ({ api: state.api, assetUrl: (url: string) => url }))
vi.mock('./shared', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./shared')>()),
  useShop: () => ({
    user: state.user,
    config: { tryon_provider: 'diagnostic', tryon_retention_hours: 24 },
  }),
}))

const product = {
  id: 'product',
  category: 'shirts',
  try_on_eligible: true,
} as ShopProduct

test('stays absent for unsupported categories', () => {
  render(<TryOnPanel product={{ ...product, category: 'bags', try_on_eligible: false }} />)
  expect(screen.queryByText('Check your photo framing')).not.toBeInTheDocument()
})

test('requires consent and clearly labels diagnostic limitations', () => {
  render(<TryOnPanel product={product} />)
  expect(screen.getByText(/does not generate a garment visualization/i)).toBeInTheDocument()
  expect(screen.getByText(/Never public/i)).toBeInTheDocument()
  expect(screen.getByLabelText(/consent to processing/i)).toBeRequired()
  expect(screen.getByLabelText(/not used for model training/i)).toBeRequired()
})

test('uploads privately, reports no real result, and deletes the job', async () => {
  state.api
    .mockResolvedValueOnce({
      id: 'job',
      status: 'needs_review',
      progress: 100,
      disclosure: 'Diagnostic only; no try-on generated.',
      result_url: null,
      error_code: null,
      diagnostics: { result_generated: false },
    })
    .mockResolvedValueOnce({
      id: 'job',
      status: 'deleted',
      progress: 100,
      disclosure: 'Diagnostic only; no try-on generated.',
      result_url: null,
      error_code: null,
      diagnostics: { user_deleted: true },
    })
  render(<TryOnPanel product={product} />)
  fireEvent.change(screen.getByLabelText('Your private photo'), {
    target: { files: [new File(['photo'], 'person.png', { type: 'image/png' })] },
  })
  fireEvent.click(screen.getByLabelText(/consent to processing/i))
  fireEvent.click(screen.getByLabelText(/not used for model training/i))
  fireEvent.submit(screen.getByRole('button', { name: 'Run private diagnostic' }).closest('form')!)
  await screen.findByText(/real try-on is not configured/i)
  expect(state.api).toHaveBeenCalledWith(
    '/try-on/products/product/jobs',
    expect.objectContaining({ method: 'POST', body: expect.any(FormData) }),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Delete private upload' }))
  await waitFor(() =>
    expect(state.api).toHaveBeenLastCalledWith('/try-on/jobs/job', { method: 'DELETE' }),
  )
})
