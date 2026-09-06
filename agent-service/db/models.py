"""
SQLAlchemy models — mirror database/schema.sql exactly.
These are read-only from the agent service's point of view; Node owns writes.
"""

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from .session import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    transactions = relationship("Transaction", back_populates="organization")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    date = Column(Date, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    type = Column(String, nullable=False)  # 'inflow' | 'outflow'
    category = Column(String, nullable=False)
    description = Column(Text)

    organization = relationship("Organization", back_populates="transactions")

    def as_dict(self):
        """Plain dict — this is what agent compute functions consume,
        so unit tests can feed them fixtures without touching the DB."""
        return {
            "id": self.id,
            "date": self.date,
            "amount": float(self.amount),
            "type": self.type,
            "category": self.category,
            "description": self.description,
        }
