from typing import Optional, List
from pydantic import BaseModel, Field

class Product(BaseModel):
    id: int
    name: str
    description: str
    category: str
    price: float
    stock: int
    rating: float
    createdAt: str

    model_config = {
        "from_attributes": True
    }

class AppliedFilters(BaseModel):
    search: Optional[str] = None
    category: Optional[str] = None
    priceMin: Optional[float] = None
    priceMax: Optional[float] = None
    inStock: Optional[bool] = None
    sort: str = "createdAt"
    order: str = "desc"
    limit: int = 20

class ProductMeta(BaseModel):
    total: int
    nextCursor: Optional[str] = None
    prevCursor: Optional[str] = None
    appliedFilters: AppliedFilters

class ProductListResponse(BaseModel):
    data: List[Product]
    meta: ProductMeta

class HealthResponse(BaseModel):
    status: str
    database: str
    totalProducts: int
