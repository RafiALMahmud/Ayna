import { useEffect, useState } from 'react'
import { ArrowRight, Heart, Menu, Search, ShoppingBag, UserRound, X } from 'lucide-react'
import { api } from '../../shared/api'
import { AccountPage, AuthPage, PasswordRecovery, SupportPage } from './Account'
import { AdminPage } from './Admin'
import { CatalogPage, HomePage, ProductDetail, WishlistPage } from './Catalog'
import { CartPage, CheckoutPage } from './Checkout'
import { OrderDetail, OrdersPage } from './Orders'
import { SellerPage } from './Seller'
import { ComparePage } from './Discovery'
import { ProductAssistant } from './ProductAssistant'
import { Empty, RequireAccount, ShopProvider, go, useRoute, useShop } from './shared'
import './commerce.css'

export default function CommerceApp() {
  return (
    <ShopProvider>
      <CommerceShell />
    </ShopProvider>
  )
}

function CommerceShell() {
  const { path, params } = useRoute()
  const { user, setUser, config, cart, reloadCart, notify } = useShop()
  const [menu, setMenu] = useState(false)
  const [search, setSearch] = useState(params.get('q') || '')
  useEffect(() => {
    setMenu(false)
  }, [path])
  const count = cart?.items.reduce((n, item) => n + item.quantity, 0) || 0
  let page
  if (path === '/') page = <HomePage />
  else if (path === '/shop') page = <CatalogPage key={params.toString()} params={params} />
  else if (path.startsWith('/products/'))
    page = <ProductDetail key={path} id={path.split('/')[2]} />
  else if (path === '/cart') page = <CartPage />
  else if (path === '/compare') page = <ComparePage />
  else if (path === '/checkout')
    page = (
      <RequireAccount>
        <CheckoutPage />
      </RequireAccount>
    )
  else if (path === '/login' || path === '/register')
    page = <AuthPage register={path === '/register'} next={params.get('next') || '/account'} />
  else if (path === '/forgot-password') page = <PasswordRecovery />
  else if (path === '/reset-password')
    page = <PasswordRecovery token={params.get('token') || undefined} />
  else if (path === '/account')
    page = (
      <RequireAccount>
        <AccountPage />
      </RequireAccount>
    )
  else if (path === '/wishlist')
    page = (
      <RequireAccount>
        <WishlistPage />
      </RequireAccount>
    )
  else if (path === '/orders')
    page = (
      <RequireAccount>
        <OrdersPage />
      </RequireAccount>
    )
  else if (path.startsWith('/orders/'))
    page = (
      <RequireAccount>
        <OrderDetail id={path.split('/')[2]} placed={params.get('placed') === 'true'} />
      </RequireAccount>
    )
  else if (path === '/seller')
    page = (
      <RequireAccount seller>
        <SellerPage />
      </RequireAccount>
    )
  else if (path === '/admin')
    page = (
      <RequireAccount admin>
        <AdminPage />
      </RequireAccount>
    )
  else if (path === '/support')
    page = (
      <RequireAccount>
        <SupportPage />
      </RequireAccount>
    )
  else if (path.startsWith('/pages/')) page = <InformationPage name={path.split('/')[2]} />
  else
    page = (
      <Empty
        title="A different perspective?"
        description="We couldn't find that page. Explore the collection instead."
      />
    )
  async function logout() {
    try {
      await api('/auth/logout', { method: 'POST' })
      setUser(null)
      go('/')
      await reloadCart()
      notify('You have been signed out')
    } catch (err) {
      notify((err as Error).message)
    }
  }
  return (
    <div className="commerce">
      <div className="shop-announcement">
        <span>{config?.announcement || 'Everyday finds. A new perspective.'}</span>
        <a href="#/pages/shipping">
          Delivery details
          <ArrowRight size={12} />
        </a>
      </div>
      <header className="shop-header">
        <a className="shop-brand" href="#/" aria-label="Ayna home">
          <span>a</span>
          {config?.name || 'Ayna'}
          <i>.</i>
        </a>
        <form
          className="shop-search"
          role="search"
          onSubmit={(e) => {
            e.preventDefault()
            go(`/shop?q=${encodeURIComponent(search)}`)
          }}
        >
          <Search size={18} />
          <input
            type="search"
            aria-label="Search products"
            placeholder="Find your next favorite…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button aria-label="Submit search">
            <ArrowRight size={17} />
          </button>
        </form>
        <div className="shop-header-actions">
          <a href="#/wishlist" aria-label="Wishlist">
            <Heart size={21} />
          </a>
          <a
            href={
              user
                ? '#/account'
                : `#/login?next=${encodeURIComponent(path === '/login' || path === '/register' ? '/account' : path)}`
            }
            aria-label={user ? 'Your account' : 'Sign in'}
          >
            <UserRound size={21} />
            <span>{user ? user.name.split(' ')[0] : 'Sign in'}</span>
          </a>
          <a href="#/cart" aria-label={`Shopping bag, ${count} items`} className="shop-bag">
            <ShoppingBag size={21} />
            {count > 0 && <span>{count}</span>}
          </a>
          <button
            className="shop-mobile-menu"
            aria-label="Toggle menu"
            onClick={() => setMenu(!menu)}
          >
            {menu ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </header>
      <div className={`shop-nav-wrap ${menu ? 'open' : ''}`}>
        <nav aria-label="Shop navigation">
          <a href="#/shop" className={path === '/shop' && !params.get('category') ? 'active' : ''}>
            All finds
          </a>
          <a href="#/shop?sort=newest">New arrivals</a>
          {config?.categories
            .filter((c) => c.count > 0)
            .slice(0, 6)
            .map((c) => (
              <a
                className={params.get('category') === c.slug ? 'active' : ''}
                key={c.slug}
                href={`#/shop?category=${c.slug}`}
              >
                {c.name}
              </a>
            ))}
          <a href="#/pages/about" className="shop-nav-about">
            The Ayna perspective
            <ArrowRight size={13} />
          </a>
        </nav>
        {user && (
          <div className="shop-account-nav">
            <a href="#/orders">My orders</a>
            {['seller', 'admin'].includes(user.role) && <a href="#/seller">Seller workspace</a>}
            {user.role === 'admin' && <a href="#/admin">Administration</a>}
            <button onClick={logout}>Sign out</button>
          </div>
        )}
      </div>
      {config?.demo_mode && (
        <div className="shop-demo-banner">
          Local demo store · Sample products and test orders · No real purchases or deliveries.
        </div>
      )}
      <main className="shop-main" key={path}>
        {page}
      </main>
      <footer className="shop-footer">
        <div>
          <a className="shop-brand" href="#/">
            <span>a</span>Ayna<i>.</i>
          </a>
          <p>
            Good things, thoughtfully chosen.
            <br />A new perspective on your everyday.
          </p>
        </div>
        <div>
          <h3>Explore</h3>
          <a href="#/shop">The collection</a>
          <a href="#/shop?sort=newest">New arrivals</a>
          <a href="#/wishlist">Your favorites</a>
          <a href="#/compare">Compare products</a>
          <a href="#/orders">Your orders</a>
        </div>
        <div>
          <h3>A little help</h3>
          <a href="#/pages/shipping">Delivery</a>
          <a href="#/pages/returns">Returns</a>
          <a href="#/pages/help">Help & FAQs</a>
          <a href="#/support">Contact support</a>
        </div>
        <div>
          <h3>The Ayna perspective</h3>
          <a href="#/pages/about">About Ayna</a>
          <a href="#/register">Sell on Ayna</a>
          <a href="#/pages/privacy">Privacy</a>
          <p className="shop-small">{config?.support_email}</p>
        </div>
        <div className="shop-footer-bottom">
          <span>© {new Date().getFullYear()} Ayna. Made for your everyday.</span>
          <span>Cash on delivery · BDT pricing</span>
        </div>
      </footer>
      <ProductAssistant />
    </div>
  )
}

function InformationPage({ name }: { name: string }) {
  const { config } = useShop()
  const content: Record<string, { title: string; intro: string; sections: [string, string][] }> = {
    about: {
      title: 'A new perspective on everyday.',
      intro:
        'Ayna brings product discovery, considered shopping, and closer product experiences into one place.',
      sections: [
        [
          'Made for the way you live',
          'Browse clothing, shoes, bags, home finds, electronics, and accessories. Save your favorites, compare details, and keep every order together.',
        ],
        [
          'See the details',
          'Original product photographs are the source of truth. Selected products can include seller-approved AI-generated 3D previews. Unseen details are inferred, and mock previews are explicitly labeled.',
        ],
        [
          'An honest beginning',
          'This local demonstration uses illustrative photography and fictional product listings. No listed item is offered for actual sale in this environment.',
        ],
      ],
    },
    shipping: {
      title: 'Good things, on their way.',
      intro:
        'Your delivery address and applicable delivery charge are confirmed before you place your order.',
      sections: [
        [
          'Delivery charges',
          `The standard configured charge is ${config ? config.shipping_minor / 100 : 80} ${config?.currency || 'BDT'}. Free delivery applies at the configured threshold shown in your bag. Discounts may affect eligibility.`,
        ],
        [
          'Follow your order',
          'Open Your orders to see processing, shipment updates, and tracking numbers added by your seller. An order with multiple sellers can ship in separate packages.',
        ],
        [
          'Delivery questions',
          'Contact support from your account and include your order number. This local demonstration does not dispatch real deliveries.',
        ],
      ],
    },
    returns: {
      title: 'Let’s make it right.',
      intro: 'Keep the conversation about your purchase in one place.',
      sections: [
        [
          'Request a return',
          'After an order is delivered, open its order page and submit a return request with a reason. Support reviews each request before accepting it.',
        ],
        [
          'Cancellation',
          'You can cancel an order before fulfillment begins. Later changes and hosted-payment cancellations are handled by support.',
        ],
        [
          'Refund updates',
          'Accepted returns and recorded refunds appear on your order timeline. Cash refunds require manual handling by the store; demo payments do not transfer money.',
        ],
      ],
    },
    help: {
      title: 'A little guidance.',
      intro: 'Everything you need for a smoother everyday shop.',
      sections: [
        [
          'How do I place an order?',
          'Browse the collection, choose a size or option when available, add products to your bag, and sign in before checkout. Guest bags are saved and merged when you sign in.',
        ],
        [
          'How do I pay?',
          'Cash on delivery is available. The local demo also offers an explicitly labeled test payment flow. Hosted payment options appear only when the store configures its payment provider.',
        ],
        [
          'Where are my orders?',
          'Sign in and choose My orders. Open an order to view its items, delivery address, receipt, payment status, and fulfillment timeline.',
        ],
        [
          'How do I sell?',
          'Create a seller account, open Seller workspace, and add a product with a unique SKU, stock, price, and photos. Product sizes and options have their own inventory.',
        ],
      ],
    },
    privacy: {
      title: 'Your details stay yours.',
      intro: 'Ayna stores the information needed to maintain your account and process your orders.',
      sections: [
        [
          'Account security',
          'Passwords are stored as salted password hashes. Authentication uses expiring, HTTP-only session cookies. Changing or resetting a password signs out other sessions.',
        ],
        [
          'Order information',
          'Your shipping details are visible to the sellers fulfilling your items and to store administrators. Other shoppers cannot access your private orders, addresses, or support conversations.',
        ],
        [
          'Product photographs',
          'Private original uploads remain in private storage. Listed product galleries use resized, metadata-stripped photo derivatives.',
        ],
        [
          'This demonstration',
          'Use sample information when testing the local demo. A deployed store must supply its own approved privacy terms, operational contact details, and data-retention procedures.',
        ],
      ],
    },
  }
  const page = content[name]
  if (!page)
    return (
      <Empty title="Page not found." description="Explore the collection or contact support." />
    )
  return (
    <section className="shop-section shop-information">
      <p className="shop-kicker">THE AYNA PERSPECTIVE</p>
      <h1>{page.title}</h1>
      <p className="shop-information-intro">{page.intro}</p>
      {page.sections.map(([title, text]) => (
        <section key={title}>
          <h2>{title}</h2>
          <p>{text}</p>
        </section>
      ))}
      <a className="shop-button" href="#/shop">
        Explore the collection
        <ArrowRight size={16} />
      </a>
    </section>
  )
}
