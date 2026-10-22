from sqlalchemy import Column, Integer, String, Text, Numeric, ForeignKey, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
import enum
from ..database import Base


class ListingType(str, enum.Enum):
    venta       = "venta"
    intercambio = "intercambio"
    ambos       = "ambos"


class ListingStatus(str, enum.Enum):
    activo    = "activo"
    reservado = "reservado"
    vendido   = "vendido"


class Listing(Base):
    __tablename__ = "listings"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    coin_id     = Column(Integer, ForeignKey("coins.id", ondelete="SET NULL"), nullable=True)

    title       = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    price       = Column(Numeric(12, 2), nullable=True)
    currency    = Column(String(3), default="BOB", nullable=False)  # BOB o USD
    listing_type= Column(SAEnum(ListingType), default=ListingType.venta, nullable=False)
    status      = Column(SAEnum(ListingStatus), default=ListingStatus.activo, nullable=False)

    item_type   = Column(String(10), default="moneda", nullable=False)  # moneda | billete

    # Datos de la moneda/billete (desnormalizados para no depender del coin)
    coin_name   = Column(String(200), nullable=True)
    coin_year   = Column(Integer, nullable=True)
    coin_country= Column(String(100), nullable=True)
    coin_condition = Column(String(200), nullable=True)
    coin_material  = Column(String(100), nullable=True)
    image_url   = Column(String(500), nullable=True)
    image_back_url = Column(String(500), nullable=True)

    usd_rate          = Column(Numeric(10, 4), nullable=True)  # tasa BOB/USD al momento de publicar

    cost              = Column(Numeric(12, 2), nullable=True)   # costo de adquisición
    cost_currency     = Column(String(3), default="BOB", nullable=True)
    cost_usd_rate     = Column(Numeric(10, 4), nullable=True)   # tasa si el costo fue en USD

    sale_notes        = Column(Text, nullable=True)
    sale_price_actual = Column(Numeric(12, 2), nullable=True)
    sold_at           = Column(DateTime(timezone=True), nullable=True)

    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    # passive_deletes: la FK ya tiene ON DELETE CASCADE; sin esto, borrar al
    # usuario intentaba poner user_id = NULL y fallaba.
    seller = relationship("User", backref=backref(
        "listings", cascade="all, delete-orphan", passive_deletes=True))
    coin   = relationship("Coin", backref="listings")
