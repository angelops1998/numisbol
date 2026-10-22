import re
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Table
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from ..database import Base


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[áàäâã]", "a", text)
    text = re.sub(r"[éèëê]",  "e", text)
    text = re.sub(r"[íìïî]",  "i", text)
    text = re.sub(r"[óòöôõ]", "o", text)
    text = re.sub(r"[úùüû]",  "u", text)
    text = re.sub(r"[ñ]",     "n", text)
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    return text.strip("-")


# Tabla de asociación many-to-many
blog_post_categorias = Table(
    "blog_post_categorias",
    Base.metadata,
    Column("post_id",      Integer, ForeignKey("blog_posts.id",      ondelete="CASCADE"), primary_key=True),
    Column("categoria_id", Integer, ForeignKey("blog_categorias.id", ondelete="CASCADE"), primary_key=True),
)


class BlogCategoria(Base):
    __tablename__ = "blog_categorias"

    id     = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(80), unique=True, nullable=False)
    slug   = Column(String(80), unique=True, nullable=False, index=True)
    color  = Column(String(20), default="#B0B0D0")

    posts  = relationship("BlogPost", secondary="blog_post_categorias", back_populates="categorias")


class BlogPostImagen(Base):
    __tablename__ = "blog_post_imagenes"

    id        = Column(Integer, primary_key=True, index=True)
    post_id   = Column(Integer, ForeignKey("blog_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    url       = Column(String(500), nullable=False)
    orden     = Column(Integer, default=0)

    post = relationship("BlogPost", back_populates="imagenes")


class BlogPost(Base):
    __tablename__ = "blog_posts"

    id          = Column(Integer, primary_key=True, index=True)
    titulo      = Column(String(200), nullable=False)
    slug        = Column(String(220), unique=True, nullable=False, index=True)
    extracto    = Column(String(400), nullable=True)
    contenido   = Column(Text, nullable=False)
    portada_url = Column(String(500), nullable=True)
    autor_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    publicado   = Column(Boolean, default=True)
    vistas      = Column(Integer, default=0)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    categorias  = relationship("BlogCategoria", secondary="blog_post_categorias", back_populates="posts")
    # passive_deletes: la FK ya tiene ON DELETE CASCADE; sin esto, borrar al
    # usuario intentaba poner autor_id = NULL y fallaba.
    autor       = relationship("User", backref=backref(
        "posts", cascade="all, delete-orphan", passive_deletes=True))
    imagenes    = relationship("BlogPostImagen", back_populates="post",
                               order_by="BlogPostImagen.orden", cascade="all, delete-orphan")
    comentarios = relationship("BlogComentario", back_populates="post",
                               order_by="BlogComentario.created_at", cascade="all, delete-orphan")


class BlogComentario(Base):
    __tablename__ = "blog_comentarios"

    id         = Column(Integer, primary_key=True, index=True)
    post_id    = Column(Integer, ForeignKey("blog_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    autor_id   = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    contenido  = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    post  = relationship("BlogPost", back_populates="comentarios")
    autor = relationship("User")
