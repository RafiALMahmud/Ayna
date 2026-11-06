import { lazy, Suspense, useEffect, useState } from 'react'
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  Heart,
  Minus,
  Plus,
  ShieldCheck,
  SlidersHorizontal,
  Star,
  Truck,
} from 'lucide-react'
import { api, assetUrl } from '../../shared/api'
import {
  Empty,
  Loading,
  Notice,
  ProductCard,
  date,
  go,
  money,
  useAction,
  useResource,
  useShop,
} from './shared'
import type { Cart, ProductPage, Review, ShopProduct } from './shared'
import { RecentlyViewed } from './Discovery'
import { rememberProduct } from './discovery-state'
import { TryOnPanel } from './TryOnPanel'
const ModelViewer = lazy(() => import('../../shared/ModelViewer'))

export function HomePage() {
  const products = useResource<ProductPage>('/shop/products?sort=featured&page_size=8')
  const { config } = useShop()
  const hero = products.data?.items[0]
  return (
    <>
      <section className="shop-hero">
        <div>
          <p className="shop-kicker">A LITTLE EXTRAORDINARY, EVERY DAY</p>
          <h1>
            Find your
            <br />
            everyday,
            <br />
            <em>elevated.</em>
          </h1>
          <p>
            Good things, thoughtfully chosen. Discover pieces for your wardrobe, your home, and
            everything in between.
          </p>
          <div className="shop-hero-links">
            <a className="shop-button" href="#/shop">
              Explore the collection <ArrowRight size={17} />
            </a>
            <a href="#/shop?sort=newest">
              Just landed <ArrowUpRight size={16} />
            </a>
          </div>
          <div className="shop-hero-note">
            <span>01 / THE EVERYDAY EDIT</span>
            <span>Considered details. Endless possibilities.</span>
          </div>
        </div>
        <a className="shop-hero-photo" href={hero ? `#/products/${hero.id}` : '#/shop'}>
          {hero?.images[0] ? (
            <img src={assetUrl(hero.images[0].url)} alt={hero.name} />
          ) : (
            <div className="shop-hero-placeholder">
              <ShoppingShape />
            </div>
          )}
          <span className="shop-photo-tag">
            THE NEW PERSPECTIVE COLLECTION <ArrowUpRight size={18} />
          </span>
        </a>
      </section>
      <div className="shop-benefits">
        <span>
          <Truck size={20} />
          <div>
            Thoughtful delivery
            <small>
              {config
                ? `Free over ${money(config.free_shipping_minor, config.currency)}`
                : 'Straight to your door'}
            </small>
          </div>
        </span>
        <span>
          <ShieldCheck size={20} />
          <div>
            Shop with confidence<small>Clear prices, secure accounts</small>
          </div>
        </span>
        <span>
          <Heart size={20} />
          <div>
            Made for your everyday<small>Discover something you love</small>
          </div>
        </span>
      </div>
      <section className="shop-section">
        <div className="shop-section-title">
          <div>
            <p className="shop-kicker">YOUR NEXT FAVORITE</p>
            <h2>Good finds. Great possibilities.</h2>
          </div>
          <a href="#/shop">
            Shop all <ArrowRight size={16} />
          </a>
        </div>
        <div className="shop-category-links">
          {config?.categories
            .filter((c) => c.count > 0)
            .map((c) => (
              <a key={c.slug} href={`#/shop?category=${c.slug}`}>
                {c.name}
                <ArrowUpRight size={15} />
              </a>
            ))}
        </div>
        <Notice error={products.error} />
        {products.loading ? (
          <Loading />
        ) : products.data?.items.length ? (
          <div className="shop-product-grid">
            {products.data.items.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        ) : (
          <Empty
            title="The collection is taking shape."
            description="Our sellers are preparing their first finds. Come back soon."
          />
        )}
      </section>
      <section className="shop-editorial">
        <div>
          <p className="shop-kicker">FIND A NEW PERSPECTIVE</p>
          <h2>
            More than a good find.
            <br />A better way to see it.
          </h2>
          <p>
            Explore the details with original photographs and interactive 3D previews on selected
            products.
          </p>
          <a href="#/shop">
            Discover your next favorite <ArrowRight size={16} />
          </a>
        </div>
        <div className="shop-editorial-categories">
          {[
            ['shirts', 'Your everyday uniform'],
            ['home', 'Make room for good things'],
            ['electronics', 'Small upgrades, big possibilities'],
          ].map(([category, text]) => (
            <a href={`#/shop?category=${category}`} key={category}>
              <span>{text}</span>
              <ArrowUpRight size={24} />
            </a>
          ))}
        </div>
      </section>
      <RecentlyViewed />
    </>
  )
}
function ShoppingShape() {
  return <div className="shop-hero-shape">a</div>
}

export function CatalogPage({ params }: { params: URLSearchParams }) {
  const { config } = useShop()
  const [filters, setFilters] = useState(false)
  const q = params.get('q') || '',
    category = params.get('category') || '',
    sort = params.get('sort') || 'featured'
  const products = useResource<ProductPage>(`/shop/products?${params.toString()}`)
  function filter(key: string, value: string) {
    const next = new URLSearchParams(params)
    next.delete('page')
    if (value) next.set(key, value)
    else next.delete(key)
    go(`/shop?${next}`)
  }
  return (
    <section className="shop-section shop-catalog">
      <div className="shop-breadcrumb">
        <a href="#/">Home</a> / Collection
      </div>
      <div className="shop-section-title">
        <div>
          <p className="shop-kicker">A NEW PERSPECTIVE ON EVERYDAY</p>
          <h1>
            {q
              ? `Results for “${q}”`
              : config?.categories.find((c) => c.slug === category)?.name || 'The collection'}
          </h1>
          <p className="shop-muted">Discover pieces that fit the way you live.</p>
        </div>
        <button
          className="shop-button outline shop-mobile-filter"
          onClick={() => setFilters(!filters)}
        >
          <SlidersHorizontal size={16} />
          Filters
        </button>
      </div>
      <div className="shop-catalog-layout">
        <aside className={`shop-filters ${filters ? 'open' : ''}`}>
          <h3>Categories</h3>
          <button className={!category ? 'active' : ''} onClick={() => filter('category', '')}>
            All products
          </button>
          {config?.categories.map((c) => (
            <button
              key={c.slug}
              className={category === c.slug ? 'active' : ''}
              onClick={() => filter('category', c.slug)}
            >
              {c.name}
              <span>{c.count}</span>
            </button>
          ))}
          <h3>Price range</h3>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              const f = new FormData(e.currentTarget)
              const next = new URLSearchParams(params)
              next.delete('page')
              for (const key of ['min_price', 'max_price']) {
                const value = String(f.get(key) || '')
                if (value) next.set(key, String(Math.round(Number(value) * 100)))
                else next.delete(key)
              }
              go(`/shop?${next}`)
            }}
          >
            <div className="shop-price-inputs">
              <input
                aria-label="Minimum price"
                name="min_price"
                type="number"
                min="0"
                placeholder="Min"
                defaultValue={params.get('min_price') ? Number(params.get('min_price')) / 100 : ''}
              />
              <input
                aria-label="Maximum price"
                name="max_price"
                type="number"
                min="0"
                placeholder="Max"
                defaultValue={params.get('max_price') ? Number(params.get('max_price')) / 100 : ''}
              />
            </div>
            <button className="shop-button outline">Apply price</button>
          </form>
          <label className="shop-checkbox">
            <input
              type="checkbox"
              checked={params.get('in_stock') === 'true'}
              onChange={(e) => filter('in_stock', e.target.checked ? 'true' : '')}
            />{' '}
            In stock only
          </label>
          <button className="shop-text-button" onClick={() => go('/shop')}>
            Clear all filters
          </button>
        </aside>
        <div>
          <div className="shop-results-bar">
            <span>{products.data?.total ?? '…'} products</span>
            <label>
              Sort by{' '}
              <select value={sort} onChange={(e) => filter('sort', e.target.value)}>
                <option value="featured">Featured</option>
                <option value="newest">Newest arrivals</option>
                <option value="price_asc">Price: low to high</option>
                <option value="price_desc">Price: high to low</option>
                <option value="rating">Top rated</option>
                <option value="name">Name</option>
              </select>
            </label>
          </div>
          <Notice error={products.error} />
          {products.loading ? (
            <Loading />
          ) : products.data?.items.length ? (
            <>
              <div className="shop-product-grid catalog-grid">
                {products.data.items.map((p) => (
                  <ProductCard key={p.id} product={p} />
                ))}
              </div>
              <div className="shop-pagination">
                <button
                  className="shop-button outline"
                  disabled={products.data.page <= 1}
                  onClick={() => {
                    const next = new URLSearchParams(params)
                    next.set('page', String(products.data!.page - 1))
                    go(`/shop?${next}`)
                  }}
                >
                  Previous
                </button>
                <span>
                  Page {products.data.page} of {products.data.pages}
                </span>
                <button
                  className="shop-button outline"
                  disabled={products.data.page >= products.data.pages}
                  onClick={() => {
                    const next = new URLSearchParams(params)
                    next.set('page', String(products.data!.page + 1))
                    go(`/shop?${next}`)
                  }}
                >
                  Next
                </button>
              </div>
            </>
          ) : (
            <Empty
              title="Nothing here just yet."
              description="Try a different search or clear your filters."
            />
          )}
        </div>
      </div>
    </section>
  )
}

export function ProductDetail({ id }: { id: string }) {
  const product = useResource<ShopProduct>(`/shop/products/${id}`)
  const reviews = useResource<Review[]>(`/shop/products/${id}/reviews`)
  const [selectedImage, setSelectedImage] = useState(0)
  const [variantId, setVariant] = useState('')
  const [quantity, setQuantity] = useState(1)
  const [show3d, setShow3d] = useState(false)
  const { user, setCart, notify } = useShop()
  const action = useAction()
  useEffect(() => {
    setSelectedImage(0)
    setVariant('')
    setQuantity(1)
    setShow3d(false)
  }, [id])
  const p = product.data
  useEffect(() => {
    if (p?.id) rememberProduct(p.id)
  }, [p?.id])
  const related = useResource<ProductPage>(
    p ? `/shop/products?category=${p.category}&page_size=5` : null,
  )
  if (product.loading) return <Loading />
  if (!p)
    return (
      <>
        <Notice error={product.error} />
        <Empty
          title="This find is unavailable."
          description="Explore something else from the collection."
        />
      </>
    )
  const selected = p.variants.find((v) => v.id === variantId)
  const stock = selected ? selected.stock : p.stock
  async function add() {
    if (p!.variants.length && !variantId) {
      action.setError('Choose a product option first.')
      return
    }
    await action.run(async () => {
      setCart(
        await api<Cart>('/cart/items', {
          method: 'POST',
          body: JSON.stringify({ product_id: id, variant_id: variantId || null, quantity }),
        }),
      )
      notify('Added to your bag')
    })
  }
  return (
    <section className="shop-section">
      <div className="shop-breadcrumb">
        <a href="#/">Home</a> / <a href={`#/shop?category=${p.category}`}>{p.category}</a> /{' '}
        {p.name}
      </div>
      <div className="shop-detail">
        <div>
          <div className="shop-detail-image">
            {show3d && p.model_asset_url ? (
              <Suspense fallback={<Loading />}>
                <ModelViewer
                  mock={p.model_disclosure?.includes('Dummy mock')}
                  url={assetUrl(p.model_asset_url)}
                  photo={p.images[0] ? assetUrl(p.images[0].url) : undefined}
                />
              </Suspense>
            ) : p.images[selectedImage] ? (
              <img src={assetUrl(p.images[selectedImage].url)} alt={p.name} />
            ) : (
              <ShoppingShape />
            )}
          </div>
          <div className="shop-thumbnails">
            {p.images.map((image, index) => (
              <button
                className={!show3d && selectedImage === index ? 'active' : ''}
                key={image.id}
                aria-label={`View product photo ${index + 1}`}
                onClick={() => {
                  setSelectedImage(index)
                  setShow3d(false)
                }}
              >
                <img src={assetUrl(image.url)} alt={`${p.name}, ${image.view_tag} view`} />
              </button>
            ))}
            {p.model_asset_url && (
              <button onClick={() => setShow3d(true)}>
                3D
                <br />
                preview
              </button>
            )}
          </div>
          {show3d && <p className="shop-small shop-muted">{p.model_disclosure}</p>}
        </div>
        <div className="shop-detail-info">
          <p className="shop-kicker">{p.brand || p.category}</p>
          <h1>{p.name}</h1>
          <a
            className="shop-rating"
            href="#product-reviews"
            onClick={(e) => {
              e.preventDefault()
              document.getElementById('product-reviews')?.scrollIntoView({ behavior: 'smooth' })
            }}
          >
            <Star size={14} />
            {p.review_count ? `${p.rating} · ${p.review_count} reviews` : 'Be the first to review'}
          </a>
          <div className="shop-detail-price">
            {money(selected?.price_minor || p.price_minor, p.currency)}
            {p.compare_at_minor && <del>{money(p.compare_at_minor, p.currency)}</del>}
          </div>
          <p className="shop-description">{p.description}</p>
          {!!p.variants.length && (
            <div className="shop-options">
              <strong>Choose your option {selected && `— ${selected.label}`}</strong>
              <div>
                {p.variants.map((v) => (
                  <button
                    className={variantId === v.id ? 'active' : ''}
                    key={v.id}
                    disabled={!v.stock}
                    onClick={() => setVariant(v.id)}
                  >
                    {v.label}
                    {!v.stock && ' · sold out'}
                  </button>
                ))}
              </div>
            </div>
          )}
          <p className={`shop-stock ${stock ? '' : 'sold-out'}`}>
            {stock ? (
              <>
                <Check size={14} />
                {stock <= 5 ? `Only ${stock} left` : 'In stock and ready for your everyday'}
              </>
            ) : (
              'Currently out of stock'
            )}
          </p>
          <div className="shop-add-row">
            <div className="shop-quantity">
              <button
                aria-label="Decrease quantity"
                onClick={() => setQuantity(Math.max(1, quantity - 1))}
              >
                <Minus size={15} />
              </button>
              <span>{quantity}</span>
              <button
                aria-label="Increase quantity"
                onClick={() => setQuantity(Math.min(99, stock, quantity + 1))}
              >
                <Plus size={15} />
              </button>
            </div>
            <button className="shop-button" disabled={action.busy || !stock} onClick={add}>
              Add to bag <ArrowRight size={17} />
            </button>
            <button
              className="shop-button outline"
              aria-label="Save to wishlist"
              onClick={() => {
                if (!user) go('/login')
                else
                  void action.run(async () => {
                    await api(`/wishlist/${id}`, { method: 'PUT' })
                    notify('Saved to your wishlist')
                  })
              }}
            >
              <Heart size={19} />
            </button>
          </div>
          <Notice error={action.error} />
          <div className="shop-detail-facts">
            <span>
              <Truck size={18} />
              Delivery calculated at checkout
            </span>
            <span>
              <ShieldCheck size={18} />
              Cash on delivery available
            </span>
            <span>
              <Heart size={18} />
              Sold by {p.seller_name}
            </span>
          </div>
          <p className="shop-small shop-muted">SKU: {selected?.sku || p.sku || '—'}</p>
          <TryOnPanel product={p} />
        </div>
      </div>
      <section className="shop-reviews" id="product-reviews">
        <div className="shop-section-title">
          <div>
            <p className="shop-kicker">FROM THE COMMUNITY</p>
            <h2>Thoughts from real orders.</h2>
          </div>
          <span className="shop-rating">
            <Star size={18} />
            {p.review_count ? `${p.rating} out of 5` : 'No reviews yet'}
          </span>
        </div>
        <Notice error={reviews.error} />
        <div className="shop-review-layout">
          <div>
            {reviews.data?.length ? (
              reviews.data.map((r) => (
                <article className="shop-review" key={r.id}>
                  <div>
                    <strong>{r.author}</strong>
                    <span>{date(r.created_at)}</span>
                  </div>
                  <p className="shop-stars">
                    {'★'.repeat(r.rating)}
                    {'☆'.repeat(5 - r.rating)} <span>Verified purchase</span>
                  </p>
                  <h3>{r.title}</h3>
                  <p>{r.body}</p>
                </article>
              ))
            ) : (
              <p className="shop-muted">Your review could help someone find their next favorite.</p>
            )}
          </div>
          <form
            className="shop-form shop-review-form"
            onSubmit={(e) => {
              e.preventDefault()
              const f = new FormData(e.currentTarget)
              void action.run(async () => {
                await api(`/shop/products/${id}/reviews`, {
                  method: 'POST',
                  body: JSON.stringify({
                    rating: Number(f.get('rating')),
                    title: f.get('title'),
                    body: f.get('body'),
                  }),
                })
                notify('Your review has been saved')
                await reviews.reload()
                await product.reload()
              })
            }}
          >
            <h3>Share your perspective</h3>
            <p className="shop-small shop-muted">Available to customers after delivery.</p>
            <label>
              Rating
              <select name="rating">
                <option value="5">★★★★★ · 5</option>
                <option value="4">★★★★ · 4</option>
                <option value="3">★★★ · 3</option>
                <option value="2">★★ · 2</option>
                <option value="1">★ · 1</option>
              </select>
            </label>
            <label>
              Title
              <input name="title" required minLength={2} maxLength={160} />
            </label>
            <label>
              Your review
              <textarea name="body" required minLength={5} maxLength={2000} rows={3} />
            </label>
            <button className="shop-button" disabled={!user || action.busy}>
              {user ? 'Submit review' : 'Sign in to review'}
            </button>
            <Notice error={action.error} />
          </form>
        </div>
      </section>
      {!!related.data?.items.filter((x) => x.id !== id).length && (
        <section className="shop-section">
          <div className="shop-section-title">
            <h2>A few more good finds.</h2>
            <a href={`#/shop?category=${p.category}`}>
              Explore more <ArrowRight size={16} />
            </a>
          </div>
          <div className="shop-product-grid">
            {related.data.items
              .filter((x) => x.id !== id)
              .slice(0, 4)
              .map((x) => (
                <ProductCard key={x.id} product={x} />
              ))}
          </div>
        </section>
      )}
    </section>
  )
}

export function WishlistPage() {
  const items = useResource<ShopProduct[]>('/wishlist')
  const action = useAction()
  return (
    <section className="shop-section">
      <p className="shop-kicker">KEEP THE GOOD THINGS CLOSE</p>
      <h1>Your wishlist</h1>
      <Notice error={items.error || action.error} />
      {items.loading ? (
        <Loading />
      ) : items.data?.length ? (
        <div className="shop-product-grid">
          {items.data.map((p) => (
            <div key={p.id}>
              <ProductCard product={p} />
              <button
                className="shop-text-button"
                onClick={() =>
                  action.run(async () => {
                    await api(`/wishlist/${p.id}`, { method: 'DELETE' })
                    await items.reload()
                  })
                }
              >
                Remove from wishlist
              </button>
            </div>
          ))}
        </div>
      ) : (
        <Empty
          title="Make room for your favorites."
          description="Save a few good finds and come back whenever you're ready."
        />
      )}
    </section>
  )
}
