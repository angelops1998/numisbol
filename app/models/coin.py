from sqlalchemy import (
    Column, Integer, String, Text, Numeric,
    ForeignKey, DateTime, UniqueConstraint, Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Coin(Base):
    __tablename__ = "coins"

    id               = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Datos principales
    name             = Column(String(200), nullable=False)
    denomination     = Column(String(100), nullable=True)
    currency_unit    = Column(String(100), nullable=True)   # Boliviano, Real, Escudo, etc.
    year             = Column(Integer, nullable=True)
    country          = Column(String(100), nullable=True, default="Bolivia")
    mint             = Column(String(100), nullable=True)
    assayer          = Column(String(300), nullable=True)   # Ensayador
    material         = Column(String(100), nullable=True)   # Plata, Oro, Cobre, etc.

    # Clasificación
    condition        = Column(String(200), nullable=True)
    category         = Column(String(200), nullable=True)

    # Económico
    estimated_value  = Column(Numeric(12, 2), nullable=True)
    purchase_price   = Column(Numeric(12, 2), nullable=True)
    value_currency   = Column(String(3), nullable=False, default="BOB", server_default="BOB")
    quantity         = Column(Integer, default=1, nullable=False)

    # Descripción e imagen
    description      = Column(Text, nullable=True)
    image_url        = Column(String(500), nullable=True)
    image_back_url   = Column(String(500), nullable=True)  # reverso

    # Tipo de ítem
    tipo             = Column(String(20), nullable=False, default="moneda", server_default="moneda")

    # Visibilidad
    is_public        = Column(Boolean, default=False, nullable=False, server_default="false")

    # Metadata
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    updated_at       = Column(DateTime(timezone=True), onupdate=func.now())

    # Relación
    owner = relationship("User", backref="coins")


class CustomOption(Base):
    __tablename__ = "custom_options"
    __table_args__ = (UniqueConstraint("field_name", "value"),)

    id         = Column(Integer, primary_key=True, index=True)
    field_name = Column(String(50), nullable=False, index=True)
    value      = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
