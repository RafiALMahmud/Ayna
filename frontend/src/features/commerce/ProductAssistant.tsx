import { FormEvent, useState } from 'react'
import { LoaderCircle, MessageCircle, Send, X } from 'lucide-react'
import { api, assetUrl } from '../../shared/api'
import { money } from './shared'

type ProductCard = {
  id: string
  name: string
  price_minor: number
  currency: string
  image_url: string | null
  product_url: string
  category: string
  brand: string
  colors: string[]
  sizes: string[]
  stock: number
  try_on_eligible: boolean
  has_3d: boolean
}

type ChatResponse = {
  answer: string
  products: ProductCard[]
  mode: string
  suggestions: string[]
}

type Message = {
  role: 'customer' | 'assistant'
  text: string
  products?: ProductCard[]
  mode?: string
}

const STARTERS = [
  'Show the cheapest shirts',
  'Which items have 3D views?',
  '১৫০০ টাকার মধ্যে কালো শার্ট দেখাও',
]

export function ProductAssistant() {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      text: 'Ask me to find products by price, color, size, availability, 3D view, or virtual try-on.',
    },
  ])
  const [suggestions, setSuggestions] = useState(STARTERS)

  async function ask(question: string) {
    const clean = question.trim()
    if (!clean || busy) return
    setInput('')
    setError('')
    setBusy(true)
    setMessages((current) => [...current, { role: 'customer', text: clean }])
    try {
      const response = await api<ChatResponse>('/chat/search', {
        method: 'POST',
        body: JSON.stringify({ message: clean }),
      })
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          text: response.answer,
          products: response.products,
          mode: response.mode,
        },
      ])
      setSuggestions(response.suggestions)
    } catch (caught) {
      setError((caught as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    void ask(input)
  }

  return (
    <div className={`shop-assistant ${open ? 'open' : ''}`}>
      {open && (
        <section className="shop-assistant-panel" aria-label="Ayna product assistant">
          <header>
            <div>
              <strong>Ayna assistant</strong>
              <span>Local catalog search</span>
            </div>
            <button aria-label="Close product assistant" onClick={() => setOpen(false)}>
              <X size={19} />
            </button>
          </header>
          <div className="shop-assistant-messages" aria-live="polite">
            {messages.map((message, index) => (
              <div className={`shop-assistant-message ${message.role}`} key={index}>
                <p>{message.text}</p>
                {message.mode && message.mode !== 'ollama-rag' && (
                  <small>Verified catalog search · local model unavailable</small>
                )}
                {message.products && message.products.length > 0 && (
                  <div className="shop-assistant-products">
                    {message.products.map((product) => (
                      <a href={product.product_url} key={product.id} onClick={() => setOpen(false)}>
                        {product.image_url ? (
                          <img src={assetUrl(product.image_url)} alt="" />
                        ) : (
                          <span className="shop-assistant-placeholder">A</span>
                        )}
                        <span>
                          <strong>{product.name}</strong>
                          <small>{money(product.price_minor, product.currency)}</small>
                          <small>
                            {product.stock > 0 ? `${product.stock} available` : 'Out of stock'}
                            {product.has_3d ? ' · 3D' : ''}
                            {product.try_on_eligible ? ' · Try-on' : ''}
                          </small>
                        </span>
                      </a>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {busy && (
              <div className="shop-assistant-thinking" role="status">
                <LoaderCircle className="spin" size={17} /> Searching the live catalog…
              </div>
            )}
            {error && (
              <div className="shop-error" role="alert">
                The product assistant is unavailable. {error}
              </div>
            )}
          </div>
          <div className="shop-assistant-suggestions">
            {suggestions.slice(0, 3).map((suggestion) => (
              <button key={suggestion} disabled={busy} onClick={() => void ask(suggestion)}>
                {suggestion}
              </button>
            ))}
          </div>
          <form onSubmit={submit}>
            <input
              aria-label="Ask about Ayna products"
              maxLength={300}
              placeholder="Black shirts under 1500 taka…"
              value={input}
              onChange={(event) => setInput(event.target.value)}
            />
            <button aria-label="Send product question" disabled={busy || input.trim().length < 2}>
              <Send size={18} />
            </button>
          </form>
          <footer>Answers use current public catalog data. No private account data is shared.</footer>
        </section>
      )}
      <button
        className="shop-assistant-toggle"
        aria-label={open ? 'Close product assistant' : 'Open product assistant'}
        onClick={() => setOpen(!open)}
      >
        {open ? <X size={23} /> : <MessageCircle size={23} />}
      </button>
    </div>
  )
}
