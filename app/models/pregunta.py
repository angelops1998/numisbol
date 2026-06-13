from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Pregunta(Base):
    __tablename__ = "preguntas"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    titulo      = Column(String(200), nullable=False)
    cuerpo      = Column(Text, nullable=True)
    image_1_url = Column(String(500), nullable=True)
    image_2_url = Column(String(500), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    is_closed   = Column(Boolean, default=False)
    views       = Column(Integer, default=0)

    autor      = relationship("User", foreign_keys=[user_id])
    respuestas = relationship("Respuesta", back_populates="pregunta",
                              cascade="all, delete-orphan", order_by="Respuesta.created_at")


class Respuesta(Base):
    __tablename__ = "respuestas"

    id          = Column(Integer, primary_key=True, index=True)
    pregunta_id = Column(Integer, ForeignKey("preguntas.id", ondelete="CASCADE"), nullable=False)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    cuerpo      = Column(Text, nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    is_best     = Column(Boolean, default=False)

    pregunta = relationship("Pregunta", back_populates="respuestas")
    autor    = relationship("User", foreign_keys=[user_id])
