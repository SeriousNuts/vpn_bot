from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from .base import Base

class AdminAction(Base):
    __tablename__ = "admin_actions"
    
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, nullable=False)  # Telegram ID of admin
    action_type = Column(String(50), nullable=False)  # user_ban, subscription_extend, etc.
    target_user_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)  # Store action details
    created_at = Column(DateTime(timezone=True), server_default=func.now())
