from pydantic import BaseModel, field_validator
from typing import Optional
from decimal import Decimal
from datetime import datetime
from ..models.coin import CoinCondition, CoinCategory


class CoinBase(BaseModel):
    name: str
    denomination: Optional[str] = None
    year: Optional[int] = None
    country: Optional[str] = "Bolivia"
    mint: Optional[str] = None
    material: Optional[str] = None
    condition: Optional[CoinCondition] = None
    category: Optional[CoinCategory] = None
    estimated_value: Optional[Decimal] = None
    purchase_price: Optional[Decimal] = None
    quantity: int = 1
    description: Optional[str] = None
    image_url: Optional[str] = None
    image_back_url: Optional[str] = None

    @field_validator("year")
    @classmethod
    def year_range(cls, v):
        if v is not None and not (1 <= v <= 2100):
            raise ValueError("Año inválido")
        return v

    @field_validator("quantity")
    @classmethod
    def qty_positive(cls, v):
        if v < 1:
            raise ValueError("La cantidad debe ser al menos 1")
        return v


class CoinCreate(CoinBase):
    pass


class CoinUpdate(CoinBase):
    name: Optional[str] = None
    quantity: Optional[int] = None


class CoinResponse(CoinBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
