import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import { TryOnPanel } from './TryOnPanel'
import type { ShopProduct } from './shared'

const state = vi.hoisted(() => ({
  api: vi.fn(),
  user: { id: 'buyer', name: 'Buyer' },
  config: { tryon_provider: 'diagnostic', tryon_retention_hours: 24 },
}))
vi.mock('../../shared/api', () => ({ api: state.api, assetUrl: (url: string) => url }))
vi.mock('./shared', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./shared')>()),
  useShop: () => ({
    user: state.user,
    config: state.config,
  }),
}))

beforeEach(() => {
  state.api.mockReset()
  state.config.tryon_provider = 'diagnostic'
})

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

test('requires full-body framing for a dress', () => {
  render(<TryOnPanel product={{ ...product, category: 'dresses' }} />)
  expect(screen.getByLabelText('Framing')).toHaveValue('full_body')
  expect(screen.queryByRole('option', { name: 'Upper body' })).not.toBeInTheDocument()
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

test('recovers a persisted job after refresh and shows its real stage', async () => {
  state.config.tryon_provider = 'fashn_vton'
  state.api.mockResolvedValueOnce({
    id: 'job',
    status: 'processing',
    progress: 50,
    disclosure: 'Generated preview only.',
    result_url: null,
    error_code: null,
    diagnostics: { stage: 'human_parsing' },
  })

  render(<TryOnPanel product={product} />)

  expect(await screen.findByText(/Mapping clothing and body regions.*50%/i)).toBeInTheDocument()
  expect(state.api).toHaveBeenCalledWith('/try-on/products/product/jobs/latest')
})

test('does not claim RTX synthesis when persisted diagnostics report CPU', async () => {
  state.config.tryon_provider = 'fashn_vton'
  state.api.mockResolvedValueOnce({
    id: 'job',
    status: 'processing',
    progress: 75,
    disclosure: 'Generated preview only.',
    result_url: null,
    error_code: null,
    diagnostics: { stage: 'cuda_synthesis', runtime: { synthesis_device: 'cpu' } },
  })

  render(<TryOnPanel product={product} />)

  expect(await screen.findByText(/Generating the preview on the CPU.*75%/i)).toBeInTheDocument()
  expect(screen.queryByText(/RTX GPU/i)).not.toBeInTheDocument()
})

test('shows the persisted skin-recovery stage', async () => {
  state.config.tryon_provider = 'fashn_vton'
  state.api.mockResolvedValueOnce({
    id: 'job',
    status: 'processing',
    progress: 90,
    disclosure: 'Generated preview only.',
    result_url: null,
    error_code: null,
    diagnostics: { stage: 'skin_recovery' },
  })

  render(<TryOnPanel product={product} />)

  expect(await screen.findByText(/Recovering exposed skin tone.*90%/i)).toBeInTheDocument()
})

test('shows the persisted CUDA device on the completed result card', async () => {
  state.config.tryon_provider = 'fashn_vton'
  state.api.mockResolvedValueOnce({
    id: 'job',
    status: 'succeeded',
    progress: 100,
    disclosure: 'Generated preview only.',
    result_url: '/try-on/jobs/job/result',
    error_code: null,
    diagnostics: {
      stage: 'output_validation',
      runtime: {
        synthesis_device: 'cuda',
        cuda_device: 'NVIDIA GeForce RTX 4050 Laptop GPU',
      },
    },
  })

  render(<TryOnPanel product={product} />)

  expect(await screen.findByText('Device: NVIDIA GeForce RTX 4050 Laptop GPU')).toBeInTheDocument()
})

test('explains a persisted timeout and offers retry without deleting the source', async () => {
  state.config.tryon_provider = 'fashn_vton'
  state.api.mockResolvedValueOnce({
    id: 'job',
    status: 'failed',
    progress: 100,
    disclosure: 'Generated preview only.',
    result_url: null,
    error_code: 'TRYON_TIMEOUT',
    diagnostics: { stage: 'failed', failed_stage: 'pose_detection' },
  })

  render(<TryOnPanel product={product} />)

  expect(await screen.findByText(/15-minute safety limit/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Try another photo/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Delete private upload' })).toBeInTheDocument()
  expect(screen.queryByText(/&#x20;/)).not.toBeInTheDocument()
})
