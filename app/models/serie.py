from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, Numeric, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Serie(Base):
    __tablename__ = "series"

    id          = Column(Integer, primary_key=True, index=True)
    nombre      = Column(String(200), nullable=False, unique=True)
    descripcion = Column(Text, nullable=True)
    orden       = Column(Integer, nullable=False, default=100, server_default="100")
    activo      = Column(Boolean, default=True, nullable=False, server_default="true")
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    variantes = relationship(
        "SerieVariante",
        back_populates="serie",
        cascade="all, delete-orphan",
        order_by="SerieVariante.anio, SerieVariante.id",
    )
    precios = relationship(
        "SeriePrecio",
        back_populates="serie",
        cascade="all, delete-orphan",
        order_by="SeriePrecio.fecha.desc(), SeriePrecio.id.desc()",
    )


class SerieVariante(Base):
    __tablename__ = "serie_variantes"

    id         = Column(Integer, primary_key=True, index=True)
    serie_id   = Column(Integer, ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True)
    anio       = Column(Integer, nullable=True)
    ensayador  = Column(String(100), nullable=True)
    ceca       = Column(String(100), nullable=True)
    mintage    = Column(String(50), nullable=True)   # texto: "1.200.000", "desconocido"
    nota       = Column(Text, nullable=True)          # ej: "sobrefecha 4/3" (texto libre, sin límite)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    serie = relationship("Serie", back_populates="variantes")
    precios = relationship("SeriePrecio", back_populates="variante", passive_deletes=True)

    @property
    def etiqueta(self) -> str:
        """Texto corto para mostrar la variante: '1884 · FE · Potosí'."""
        partes = []
        if self.anio:      partes.append(str(self.anio))
        if self.ensayador: partes.append(self.ensayador)
        if self.ceca:      partes.append(self.ceca)
        if self.nota:      partes.append(self.nota)
        return " · ".join(partes) if partes else f"Variante #{self.id}"


class SeriePrecio(Base):
    """Precio de referencia que el admin vio publicado (eBay, MercadoLibre, subastas…).

    Solo sirve para armar un estimativo; no es un precio de la plataforma.
    Si variante_id es NULL, el precio vale para la serie en general.
    """
    __tablename__ = "serie_precios"

    id          = Column(Integer, primary_key=True, index=True)
    serie_id    = Column(Integer, ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True)
    variante_id = Column(Integer, ForeignKey("serie_variantes.id", ondelete="CASCADE"), nullable=True, index=True)
    monto       = Column(Numeric(12, 2), nullable=False)
    moneda      = Column(String(3), nullable=False, default="USD", server_default="USD")   # USD | BOB
    tipo        = Column(String(10), nullable=False, default="oferta", server_default="oferta")  # oferta | vendido
    estado      = Column(String(30), nullable=True)    # conservación: "MBC", "XF", "MS63"…
    fuente      = Column(String(100), nullable=True)   # "eBay", "MercadoLibre", "Facebook"…
    url         = Column(String(500), nullable=True)
    fecha       = Column(Date, nullable=True)
    nota        = Column(Text, nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    serie    = relationship("Serie", back_populates="precios")
    variante = relationship("SerieVariante", back_populates="precios")
