from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from ..database import Base


class Anuncio(Base):
    __tablename__ = "anuncios"

    id          = Column(Integer, primary_key=True, index=True)
    titulo      = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=True)
    imagen_url  = Column(String(500), nullable=False)
    activo      = Column(Boolean, default=True)
    orden       = Column(Integer, default=0)   # menor = primero
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
