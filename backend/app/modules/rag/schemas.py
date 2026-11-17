from pydantic import BaseModel, Field


class ChatIn(BaseModel):
    message: str = Field(min_length=2, max_length=300)


class ChatProduct(BaseModel):
    id: str
    name: str
    price_minor: int
    currency: str
    image_url: str | None
    product_url: str
    category: str
    brand: str
    colors: list[str]
    sizes: list[str]
    stock: int
    try_on_eligible: bool
    has_3d: bool


class ChatOut(BaseModel):
    answer: str
    products: list[ChatProduct]
    mode: str
    filters: dict
    suggestions: list[str]
