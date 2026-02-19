# app/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    stripe_connect_id = Column(String, unique=True)  # The connected account ID
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    events = relationship("RecoveryEvent", back_populates="user")

class RecoveryEvent(Base):
    __tablename__ = "recovery_events"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    stripe_customer_id = Column(String)
    invoice_id = Column(String)
    amount_due = Column(Float)
    status = Column(String)  # 'pending', 'recovered', 'failed'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="events")
