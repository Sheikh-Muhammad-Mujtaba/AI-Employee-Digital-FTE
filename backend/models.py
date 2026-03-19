"""SQLAlchemy ORM models."""

from sqlalchemy import Column, Integer, String
from database import Base


class User(Base):
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, index=True)
    username: str = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password: str = Column(String(255), nullable=False)
    role: str = Column(String(20), nullable=False, default="admin")
