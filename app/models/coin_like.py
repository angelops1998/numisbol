from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from ..database import Base


class CoinLike(Base):
    """Un «me gusta» de un usuario a una pieza pública."""

    __tablename__ = "coin_likes"
    __table_args__ = (UniqueConstraint("coin_id", "user_id", name="uq_coin_likes_coin_user"),)

    id         = Column(Integer, primary_key=True, index=True)
    coin_id    = Column(Integer, ForeignKey("coins.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # passive_deletes: la FK ya tiene ON DELETE CASCADE en la base
    coin = relationship("Coin", backref=backref(
        "likes", cascade="all, delete-orphan", passive_deletes=True))
    user = relationship("User", backref=backref(
        "coin_likes", cascade="all, delete-orphan", passive_deletes=True))
