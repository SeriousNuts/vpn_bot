from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base
from ..enums import SubscriptionStatus, ProtocolType

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_name = Column(String(50), nullable=False)  # 1_month, 3_months, etc.
    price = Column(Float, nullable=False)
    duration_days = Column(Integer, nullable=False)
    status = Column(String(20), default=SubscriptionStatus.PENDING)
    protocol = Column(String(20), default=ProtocolType.VLESS)
    config_data = Column(JSON, nullable=True)  # Store VPN configuration
    subscription_url = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    on_hold_timeout = Column(Integer)
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")
    payments = relationship("Payment", back_populates="subscription")
