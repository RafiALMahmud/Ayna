from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ORMOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(ORMOut):
    id: str
    email: str
    name: str
    role: str
    is_active: bool


class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=128)
    role: Literal["customer", "seller"] = "customer"


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class ProfileIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class PasswordIn(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class ForgotIn(BaseModel):
    email: str = Field(max_length=254)


class ResetIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=10, max_length=128)


class MessageOut(BaseModel):
    message: str
    development_reset_url: str | None = None


class AddressIn(BaseModel):
    label: str = Field(default="Home", min_length=1, max_length=50)
    recipient: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=6, max_length=30, pattern=r"^[+0-9 ()-]+$")
    street: str = Field(min_length=5, max_length=300)
    city: str = Field(min_length=2, max_length=100)
    postal_code: str = Field(min_length=2, max_length=20)
    country: str = Field(default="BD", pattern="^[A-Z]{2}$")


class AddressOut(AddressIn, ORMOut):
    id: str


class CategoryIn(BaseModel):
    slug: str = Field(min_length=2, max_length=32, pattern="^[a-z0-9-]+$")
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=300)
    is_active: bool = True


class VariantIn(BaseModel):
    id: UUID | None = None
    label: str = Field(min_length=1, max_length=100)
    sku: str = Field(min_length=1, max_length=80)
    size: str = Field(default="", max_length=30)
    color: str = Field(default="", max_length=40)
    stock: int = Field(ge=0, le=1000000)
    price_minor: int = Field(ge=1, le=100000000)
    is_active: bool = True


class VariantOut(ORMOut):
    id: str
    label: str
    sku: str
    size: str
    color: str
    stock: int
    price_minor: int
    is_active: bool


class ListingIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=32, pattern="^[a-z0-9-]+$")
    description: str = Field(default="", max_length=3000)
    brand: str = Field(default="", max_length=100)
    sku: str = Field(min_length=1, max_length=80)
    price_minor: int = Field(ge=1, le=100000000)
    compare_at_minor: int | None = Field(default=None, ge=1, le=100000000)
    stock: int = Field(ge=0, le=1000000)
    is_listed: bool = False

    @model_validator(mode="after")
    def compare_price(self):
        if self.compare_at_minor is not None and self.compare_at_minor < self.price_minor:
            raise ValueError("Compare price cannot be lower than price")
        return self


class ShopImage(BaseModel):
    id: str
    url: str
    view_tag: str


class ShopProduct(BaseModel):
    id: str
    name: str
    category: str
    description: str
    brand: str
    sku: str | None
    price_minor: int
    compare_at_minor: int | None
    stock: int
    currency: str
    images: list[ShopImage]
    variants: list[VariantOut]
    rating: float
    review_count: int
    seller_name: str
    is_listed: bool
    is_archived: bool
    featured: bool
    model_asset_url: str | None
    model_disclosure: str | None
    try_on_eligible: bool


class ProductPage(BaseModel):
    items: list[ShopProduct]
    total: int
    page: int
    pages: int


class CategorySummary(BaseModel):
    slug: str
    name: str
    count: int


class StoreConfig(BaseModel):
    name: str
    tagline: str
    currency: str
    shipping_minor: int
    free_shipping_minor: int
    tax_basis_points: int
    support_email: str
    announcement: str
    categories: list[CategorySummary]
    payment_methods: list[str]
    demo_mode: bool
    tryon_provider: Literal["disabled", "diagnostic"]
    tryon_retention_hours: int


class StoreSettingsIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    tagline: str = Field(max_length=160)
    shipping_minor: int = Field(ge=0, le=1000000)
    free_shipping_minor: int = Field(ge=0, le=100000000)
    tax_basis_points: int = Field(ge=0, le=10000)
    support_email: str = Field(max_length=254)
    announcement: str = Field(max_length=200)


class CartIn(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    quantity: int = Field(default=1, ge=1, le=99)


class QuantityIn(BaseModel):
    quantity: int = Field(ge=1, le=99)


class CartLine(BaseModel):
    id: str
    product: ShopProduct
    variant_id: str | None
    variant_label: str
    quantity: int
    unit_price_minor: int
    line_total_minor: int
    available_stock: int
    available: bool


class QuoteIn(BaseModel):
    coupon_code: str = Field(default="", max_length=32)


class CartOut(BaseModel):
    items: list[CartLine]
    subtotal_minor: int
    discount_minor: int
    shipping_minor: int
    tax_minor: int
    total_minor: int
    currency: str
    coupon_code: str | None


class CheckoutIn(QuoteIn):
    address: AddressIn
    payment_method: Literal["cod", "demo", "stripe"] = "cod"
    notes: str = Field(default="", max_length=1000)


class OrderItemOut(ORMOut):
    id: str
    product_id: str
    name: str
    variant_label: str
    sku: str
    unit_price_minor: int
    quantity: int
    fulfillment_status: str
    tracking_number: str
    courier: str


class OrderEventOut(ORMOut):
    status: str
    message: str
    created_at: datetime


class OrderOut(BaseModel):
    id: str
    number: str
    status: str
    payment_method: str
    payment_status: str
    currency: str
    subtotal_minor: int
    discount_minor: int
    shipping_minor: int
    tax_minor: int
    total_minor: int
    coupon_code: str | None
    shipping_address: dict
    notes: str
    return_reason: str
    created_at: datetime
    items: list[OrderItemOut]
    events: list[OrderEventOut]


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: str = Field(min_length=2, max_length=160)
    body: str = Field(min_length=5, max_length=2000)


class ReviewOut(BaseModel):
    id: str
    author: str
    rating: int
    title: str
    body: str
    verified_purchase: bool = True
    created_at: datetime


class CouponIn(BaseModel):
    code: str = Field(min_length=2, max_length=32, pattern="^[a-zA-Z0-9_-]+$")
    discount_percent: int = Field(default=0, ge=0, le=100)
    discount_minor: int = Field(default=0, ge=0, le=100000000)
    minimum_minor: int = Field(default=0, ge=0, le=100000000)
    max_uses: int = Field(default=100, ge=1, le=1000000)
    is_active: bool = True
    expires_at: datetime | None = None

    @field_validator("code")
    @classmethod
    def uppercase(cls, value):
        return value.upper()


class CouponOut(CouponIn, ORMOut):
    used_count: int


class FulfillIn(BaseModel):
    status: Literal["processing", "shipped", "delivered"]
    tracking_number: str = Field(default="", max_length=100)
    courier: str = Field(default="", max_length=80)


class ReturnIn(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class AdminOrderIn(BaseModel):
    action: Literal["cancel", "approve_return", "reject_return", "mark_cod_paid", "refund"]


class UserRoleIn(BaseModel):
    role: Literal["customer", "seller", "admin"]
    is_active: bool


class ProductModerationIn(BaseModel):
    is_listed: bool
    featured: bool


class NotificationOut(ORMOut):
    id: str
    title: str
    message: str
    is_read: bool
    created_at: datetime


class TicketIn(BaseModel):
    subject: str = Field(min_length=3, max_length=160)
    message: str = Field(min_length=10, max_length=3000)


class TicketOut(ORMOut):
    id: str
    user_id: str
    subject: str
    message: str
    status: str
    response: str
    created_at: datetime


class TicketReplyIn(BaseModel):
    response: str = Field(min_length=2, max_length=3000)
    status: Literal["open", "resolved"] = "resolved"
