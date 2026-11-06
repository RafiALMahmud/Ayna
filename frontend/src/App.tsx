import { useEffect, useState } from 'react'
import { Box, LayoutGrid, ShoppingBag, ArrowUpRight, Layers3, CircleHelp } from 'lucide-react'
import { api, API_BASE } from './shared/api'
import type { Config } from './shared/api'
import { Studio } from './features/seller/Studio'
import { Storefront } from './features/storefront/Storefront'
import CommerceApp from './features/commerce/CommerceApp'

export function StudioApp() {
  const [tab, setTab] = useState<'studio' | 'store'>('studio')
  const [config, setConfig] = useState<Config | null>(null)
  const [error, setError] = useState('')
  const load = () =>
    api<Config>('/config')
      .then((c) => {
        setConfig(c)
        setError('')
      })
      .catch((e) => setError(e.message))
  useEffect(() => {
    load()
  }, [])
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="Ayna home">
          <span className="brand-mark">a</span>Ayna<span className="brand-period">.</span>
        </a>
        <a className="docs-link" href="#/">
          Back to Ayna shop
        </a>
        <div className="workspace-name">
          <span className="workspace-avatar">A</span>
          <div>
            Ayna workspace<small>Product experiences</small>
          </div>
          <span className="workspace-chevron">⌄</span>
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav aria-label="Main navigation">
          <button className={tab === 'studio' ? 'active' : ''} onClick={() => setTab('studio')}>
            <LayoutGrid size={18} /> Product studio
            <span className="nav-dot" />
          </button>
          <button className={tab === 'store' ? 'active' : ''} onClick={() => setTab('store')}>
            <ShoppingBag size={18} /> Storefront
            <ArrowUpRight size={15} />
          </button>
        </nav>
        <div className="sidebar-bottom">
          <div className="mock-card">
            <Layers3 size={22} />
            <h3>A space to experiment.</h3>
            <p>
              {config?.provider !== 'mock'
                ? 'Hosted reconstruction is enabled. New generation requests use credits.'
                : 'Explore the complete workflow with a free, deterministic mock provider.'}
            </p>
            <span>
              <span className="status-dot" />{' '}
              {config?.provider !== 'mock'
                ? `${config?.provider === 'tripo' ? 'Tripo' : 'Meshy'} enabled`
                : 'Mock mode is on'}
            </span>
          </div>
          <a className="docs-link" href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">
            <CircleHelp size={17} /> API documentation
            <ArrowUpRight size={14} />
          </a>
          <div className="profile">
            <span className="profile-avatar">D1</span>
            <div>
              {config?.seller_authenticated ? 'Seller account' : 'Demo seller'}
              <small>
                {config?.seller_authenticated
                  ? 'Authenticated workspace'
                  : 'Local development account'}
              </small>
            </div>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <span>
            <Box size={16} /> Workspace <span className="breadcrumb">/</span>{' '}
            <strong>{tab === 'studio' ? 'Product studio' : 'Storefront'}</strong>
          </span>
          <span className="environment">
            <span className="status-dot" />
            {config ? 'Local development' : 'Connecting to API'}
          </span>
        </header>
        <main>
          {error ? (
            <div className="connection-error">
              <h1>Let's reconnect.</h1>
              <p role="alert">Ayna API is unavailable. {error}</p>
              <button className="button primary" onClick={load}>
                Retry connection
              </button>
            </div>
          ) : config ? (
            tab === 'studio' ? (
              <Studio config={config} />
            ) : (
              <Storefront />
            )
          ) : (
            <p className="muted">Opening your Ayna workspace…</p>
          )}
          <footer>
            <span>Ayna — a closer connection to your products.</span>
            <span>
              Made for a new perspective <span className="footer-star">✳</span>
            </span>
          </footer>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const change = () => setHash(window.location.hash)
    window.addEventListener('hashchange', change)
    return () => window.removeEventListener('hashchange', change)
  }, [])
  return hash.startsWith('#/studio') ? <StudioApp /> : <CommerceApp />
}
