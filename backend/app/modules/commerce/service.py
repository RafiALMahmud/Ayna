import math
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.common.config import get_settings
from app.common.identity import aware
from app.common.models import Product
from app.common.storage import asset_url
from app.modules.commerce.models import (
    CartItem,
    Category,
    Coupon,
    Notification,
    Order,
    OrderEvent,
    OrderItem,
    Review,
    StoreSettings,
    User,
    Variant,
)
from app.modules.commerce.schemas import (
    CartLine,
    CartOut,
    CategorySummary,
    OrderEventOut,
    OrderItemOut,
    OrderOut,
    ShopImage,
    ShopProduct,
    StoreConfig,
    VariantOut,
)
from app.modules.generation.providers import disclosure
from app.modules.generation.tasks import latest_job

DEFAULT_CATEGORIES = {
    "bags": "Bags",
    "shoes": "Shoes",
    "shirts": "Clothing",
    "pants": "Trousers",
    "electronics": "Electronics",
    "home": "Home & living",
    "accessories": "Accessories",
    "beauty": "Beauty",
}


def store_values(db) -> dict:
    store = db.get(StoreSettings, 1)
    return {
        "name": store.name if store else "Ayna",
        "tagline": store.tagline if store else "Everyday finds. A new perspective.",
        "shipping_minor": store.shipping_minor if store else 8000,
        "free_shipping_minor": store.free_shipping_minor if store else 300000,
        "tax_basis_points": store.tax_basis_points if store else 0,
        "support_email": store.support_email if store else "support@example.com",
        "announcement": store.announcement if store else "Free delivery on orders over ৳3,000",
    }


def store_config(db) -> StoreConfig:
    settings = get_settings()
    all_categories = db.scalars(select(Category)).all()
    categories = [category for category in all_categories if category.is_active]
    counts = dict(
        db.execute(
            select(Product.category, func.count(Product.id))
            .where(Product.is_listed.is_(True), Product.is_archived.is_(False))
            .group_by(Product.category)
        ).all()
    )
    category_data = (
        [{"slug": c.slug, "name": c.name, "count": counts.get(c.slug, 0)} for c in categories]
        if all_categories
        else [
            {"slug": slug, "name": name, "count": counts.get(slug, 0)}
            for slug, name in DEFAULT_CATEGORIES.items()
        ]
    )
    methods = ["cod"]
    if settings.demo_payments_enabled and settings.environment != "production":
        methods.append("demo")
    if settings.stripe_secret_key and settings.stripe_webhook_secret:
        methods.append("stripe")
    return StoreConfig(
        **store_values(db),
        currency=settings.currency,
        categories=[CategorySummary.model_validate(c) for c in category_data],
        payment_methods=methods,
        demo_mode=settings.environment != "production",
        tryon_provider=settings.tryon_provider,
        tryon_retention_hours=settings.tryon_retention_hours,
    )


def listed(db, product_id: str, lock=False) -> Product:
    stmt = select(Product).where(
        Product.id == product_id, Product.is_listed.is_(True), Product.is_archived.is_(False)
    )
    product = db.scalar(stmt.with_for_update() if lock else stmt)
    if product is None:
        raise HTTPException(404, "Product not found")
    seller = db.get(User, product.seller_id)
    if seller and not seller.is_active:
        raise HTTPException(404, "Product not found")
    category = db.get(Category, product.category)
    if category and not category.is_active:
        raise HTTPException(404, "Product not found")
    return product


def product_view(db, product: Product, private=False) -> ShopProduct:
    all_variants = db.scalars(
        select(Variant).where(Variant.product_id == product.id).order_by(Variant.label)
    ).all()
    active_variants = [v for v in all_variants if v.is_active]
    variants = all_variants if private else active_variants
    rating, count = db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.product_id == product.id, Review.is_visible.is_(True)
        )
    ).one()
    seller = db.get(User, product.seller_id)
    model_url = None
    if private or product.publish_status == "approved":
        job = latest_job(db, product.id)
        if job and job.status == "succeeded" and job.model_key:
            model_url = (
                asset_url("model", job.id, product.seller_id)
                if private
                else (f"/api/v1/shop/products/{product.id}/model")
            )
    return ShopProduct(
        id=product.id,
        name=product.name,
        category=product.category,
        description=product.description,
        brand=product.brand,
        sku=product.sku,
        price_minor=product.price_minor,
        compare_at_minor=product.compare_at_minor,
        stock=sum(v.stock for v in active_variants) if all_variants else product.stock,
        currency=get_settings().currency,
        images=[
            ShopImage(
                id=i.id,
                view_tag=i.view_tag,
                url=asset_url("image", i.id, product.seller_id)
                if private
                else f"/api/v1/shop/products/{product.id}/images/{i.id}",
            )
            for i in product.images
        ],
        variants=[VariantOut.model_validate(v) for v in variants],
        rating=round(rating or 0, 1),
        review_count=count,
        seller_name=seller.name if seller else "Ayna seller",
        is_listed=product.is_listed,
        is_archived=product.is_archived,
        featured=product.featured,
        model_asset_url=model_url,
        model_disclosure=disclosure(job.provider) if model_url and job else None,
        try_on_eligible=product.category in {"shirts", "pants", "shoes"},
    )


def selection(db, product: Product, variant_key: str, lock=False):
    has_variants = db.scalar(select(Variant.id).where(Variant.product_id == product.id).limit(1))
    if variant_key == "default":
        if has_variants:
            raise HTTPException(422, "Choose a size or product option")
        return product, product.price_minor, "", product.sku or ""
    stmt = select(Variant).where(
        Variant.id == variant_key, Variant.product_id == product.id, Variant.is_active.is_(True)
    )
    variant = db.scalar(stmt.with_for_update() if lock else stmt)
    if variant is None:
        raise HTTPException(409, "The selected option is no longer available")
    return variant, variant.price_minor, variant.label, variant.sku


def cart_quote(db, user_id: str, coupon_code="", lock=False) -> CartOut:
    rows = db.scalars(
        select(CartItem)
        .where(CartItem.user_id == user_id)
        .order_by(CartItem.product_id, CartItem.variant_key)
    ).all()
    lines = []
    for row in rows:
        product = (
            db.scalar(select(Product).where(Product.id == row.product_id).with_for_update())
            if lock
            else db.get(Product, row.product_id)
        )
        if product is None:
            continue
        try:
            inventory, price, label, _ = selection(db, product, row.variant_key, lock)
            stock = inventory.stock
        except HTTPException:
            price, label, stock = product.price_minor, "Unavailable option", 0
        seller = db.get(User, product.seller_id)
        available = product.is_listed and not product.is_archived and stock >= row.quantity
        available = available and (seller is None or seller.is_active)
        lines.append(
            CartLine(
                id=row.id,
                product=product_view(db, product),
                variant_id=None if row.variant_key == "default" else row.variant_key,
                variant_label=label,
                quantity=row.quantity,
                unit_price_minor=price,
                line_total_minor=price * row.quantity,
                available_stock=stock,
                available=available,
            )
        )
    subtotal = sum(line.line_total_minor for line in lines)
    discount = 0
    coupon_code = coupon_code.strip().upper()
    if coupon_code:
        stmt = select(Coupon).where(Coupon.code == coupon_code)
        coupon = db.scalar(stmt.with_for_update() if lock else stmt)
        if (
            coupon is None
            or not coupon.is_active
            or coupon.used_count >= coupon.max_uses
            or (coupon.expires_at and aware(coupon.expires_at) <= datetime.now(UTC))
        ):
            raise HTTPException(422, "Coupon is invalid or expired")
        if subtotal < coupon.minimum_minor:
            raise HTTPException(422, "The order does not meet this coupon's minimum")
        discount = min(subtotal, subtotal * coupon.discount_percent // 100 + coupon.discount_minor)
    values = store_values(db)
    net = subtotal - discount
    shipping = values["shipping_minor"] if lines and net < values["free_shipping_minor"] else 0
    tax = (net * values["tax_basis_points"] + 5000) // 10000
    return CartOut(
        items=lines,
        subtotal_minor=subtotal,
        discount_minor=discount,
        shipping_minor=shipping,
        tax_minor=tax,
        total_minor=net + shipping + tax,
        currency=get_settings().currency,
        coupon_code=coupon_code or None,
    )


def order_view(db, order: Order, seller_id: str | None = None) -> OrderOut:
    stmt = select(OrderItem).where(OrderItem.order_id == order.id)
    if seller_id:
        stmt = stmt.where(OrderItem.seller_id == seller_id)
    items = db.scalars(stmt).all()
    events = db.scalars(
        select(OrderEvent).where(OrderEvent.order_id == order.id).order_by(OrderEvent.created_at)
    ).all()
    # Sellers see only their own item totals and fulfillment details; customer totals stay private.
    subtotal = (
        sum(i.unit_price_minor * i.quantity for i in items) if seller_id else order.subtotal_minor
    )
    return OrderOut(
        id=order.id,
        number=order.number,
        status=order.status,
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        currency=order.currency,
        subtotal_minor=subtotal,
        discount_minor=0 if seller_id else order.discount_minor,
        shipping_minor=0 if seller_id else order.shipping_minor,
        tax_minor=0 if seller_id else order.tax_minor,
        total_minor=subtotal if seller_id else order.total_minor,
        coupon_code=None if seller_id else order.coupon_code,
        shipping_address=order.shipping_address,
        notes=order.notes,
        return_reason=order.return_reason,
        created_at=order.created_at,
        items=[OrderItemOut.model_validate(i) for i in items],
        events=[] if seller_id else [OrderEventOut.model_validate(e) for e in events],
    )


def order_event(db, order: Order, message: str):
    db.add(OrderEvent(order_id=order.id, status=order.status, message=message))
    db.add(Notification(user_id=order.user_id, title=f"Order {order.number}", message=message))


def release_stock(db, order: Order):
    if order.stock_released:
        return
    for item in db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)):
        model = Product if item.variant_key == "default" else Variant
        inventory_id = item.product_id if item.variant_key == "default" else item.variant_key
        db.execute(
            update(model).where(model.id == inventory_id).values(stock=model.stock + item.quantity)
        )
    order.stock_released = True
    if order.coupon_code:
        db.execute(
            update(Coupon)
            .where(Coupon.code == order.coupon_code, Coupon.used_count > 0)
            .values(used_count=Coupon.used_count - 1)
        )


def aggregate_fulfillment(db, order: Order):
    if order.status in {"cancelled", "return_requested", "returned"}:
        return
    states = db.scalars(
        select(OrderItem.fulfillment_status).where(OrderItem.order_id == order.id)
    ).all()
    if states and all(s == "delivered" for s in states):
        order.status = "delivered"
    elif states and all(s in {"shipped", "delivered"} for s in states):
        order.status = "shipped"
    elif any(s != "pending" for s in states):
        order.status = "processing"


def page_count(total: int, size: int) -> int:
    return max(1, math.ceil(total / size))
