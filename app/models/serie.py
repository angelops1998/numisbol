from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
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

    @property
    def etiqueta(self) -> str:
        """Texto corto para mostrar la variante: '1884 · FE · Potosí'."""
        partes = []
        if self.anio:      partes.append(str(self.anio))
        if self.ensayador: partes.append(self.ensayador)
        if self.ceca:      partes.append(self.ceca)
        if self.nota:      partes.append(self.nota)
        return " · ".join(partes) if partes else f"Variante #{self.id}"
