from sqlalchemy import Column, String, Text
from ..database import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    key   = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
