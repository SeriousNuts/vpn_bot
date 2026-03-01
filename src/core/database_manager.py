"""
Advanced Database Manager with atomic transactions and connection recovery
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, Type, TypeVar, Generic, List, Dict, Any, Callable
from functools import wraps
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine,
    AsyncEngine
)
from sqlalchemy.exc import (
    SQLAlchemyError, DisconnectionError, OperationalError,
    InterfaceError, DatabaseError
)
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import select, update, delete, insert, and_, or_
from sqlalchemy.sql import Select, Update, Delete, Insert
from sqlalchemy.sql.expression import func

from src.core.config import settings
from src.models.base import Base
from src.models import User, Subscription, Payment, NotificationLog, AdminAction

logger = logging.getLogger(__name__)

T = TypeVar('T')

class DatabaseManager:
    """
    Advanced database manager with automatic connection recovery,
    atomic transactions, and convenient CRUD operations
    """
    
    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None
        self._connection_retries = 3
        self._retry_delay = 1.0
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize database connection and session factory"""
        if self._initialized:
            return
        
        try:
            # Create async engine with optimized settings
            self._engine = create_async_engine(
                settings.database_url,
                echo=settings.log_level.upper() == "DEBUG",
                pool_size=20,
                max_overflow=30,
                pool_pre_ping=True,
                pool_recycle=3600,
                pool_timeout=30,
                connect_args={
                    "command_timeout": 60,
                    "server_settings": {
                        "application_name": "vpn_bot",
                        "jit": "off"
                    }
                }
            )
            
            # Create session factory
            self._session_factory = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False
            )
            
            # Test connection
            async with self._engine.begin() as conn:
                await conn.execute("SELECT 1")
            
            self._initialized = True
            logger.info("✅ Database manager initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database manager: {e}")
            raise
    
    async def close(self) -> None:
        """Close database connections"""
        if self._engine:
            await self._engine.dispose()
            self._initialized = False
            logger.info("Database connections closed")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncSession:
        """
        Get database session with automatic connection recovery
        """
        if not self._initialized:
            await self.initialize()
        
        for attempt in range(self._connection_retries):
            try:
                async with self._session_factory() as session:
                    try:
                        yield session
                        await session.commit()
                        break
                    except (DisconnectionError, OperationalError, InterfaceError) as e:
                        await session.rollback()
                        logger.warning(f"Connection error (attempt {attempt + 1}): {e}")
                        if attempt == self._connection_retries - 1:
                            raise
                        await asyncio.sleep(self._retry_delay * (2 ** attempt))
                    except Exception as e:
                        await session.rollback()
                        logger.error(f"Transaction failed: {e}")
                        raise
            except Exception as e:
                if attempt == self._connection_retries - 1:
                    logger.error(f"Failed to get database session after {self._connection_retries} attempts: {e}")
                    raise
                await asyncio.sleep(self._retry_delay * (2 ** attempt))
    
    def atomic(self, func_to_call: Callable) -> Callable:
        """
        Decorator for atomic transactions with automatic rollback on error
        """
        @wraps(func_to_call)
        async def wrapper(*args, **kwargs):
            async with self.get_session() as session:
                try:
                    return await func_to_call(session, *args, **kwargs)
                except Exception as e:
                    logger.error(f"Atomic transaction failed in {func_to_call.__name__}: {e}")
                    raise
        return wrapper
    
    # Generic CRUD operations
    async def create(self, model: Type[T], **kwargs) -> T:
        """Create a new record"""
        async with self.get_session() as session:
            try:
                instance = model(**kwargs)
                session.add(instance)
                await session.flush()
                await session.refresh(instance)
                logger.debug(f"Created {model.__name__}: {instance.id}")
                return instance
            except Exception as e:
                logger.error(f"Failed to create {model.__name__}: {e}")
                raise
    
    async def get_by_id(self, model: Type[T], id: int) -> Optional[T]:
        """Get record by ID"""
        async with self.get_session() as session:
            try:
                result = await session.execute(select(model).where(model.id == id))
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Failed to get {model.__name__} by ID {id}: {e}")
                raise
    
    async def get_by_field(self, model: Type[T], field: str, value: Any) -> Optional[T]:
        """Get record by field value"""
        async with self.get_session() as session:
            try:
                result = await session.execute(select(model).where(getattr(model, field) == value))
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Failed to get {model.__name__} by {field}={value}: {e}")
                raise
    
    async def get_all(self, model: Type[T], 
                     filters: Optional[Dict[str, Any]] = None,
                     limit: Optional[int] = None,
                     offset: Optional[int] = None,
                     order_by: Optional[str] = None) -> List[T]:
        """Get all records with optional filters, pagination and ordering"""
        async with self.get_session() as session:
            try:
                query = select(model)
                
                # Apply filters
                if filters:
                    for field, value in filters.items():
                        if hasattr(model, field):
                            query = query.where(getattr(model, field) == value)
                
                # Apply ordering
                if order_by and hasattr(model, order_by):
                    query = query.order_by(getattr(model, order_by))
                
                # Apply pagination
                if offset:
                    query = query.offset(offset)
                if limit:
                    query = query.limit(limit)
                
                result = await session.execute(query)
                return result.scalars().all()
            except Exception as e:
                logger.error(f"Failed to get all {model.__name__}: {e}")
                raise
    
    async def update(self, model: Type[T], 
                    id: int, **kwargs) -> Optional[T]:
        """Update record by ID"""
        async with self.get_session() as session:
            try:
                result = await session.execute(
                    update(model).where(model.id == id).values(**kwargs).returning(model)
                )
                instance = result.scalar_one_or_none()
                if instance:
                    await session.refresh(instance)
                    logger.debug(f"Updated {model.__name__} {id}")
                return instance
            except Exception as e:
                logger.error(f"Failed to update {model.__name__} {id}: {e}")
                raise
    
    async def update_by_field(self, model: Type[T],
                             field: str, value: Any, **kwargs) -> List[T]:
        """Update records by field value"""
        async with self.get_session() as session:
            try:
                result = await session.execute(
                    update(model).where(getattr(model, field) == value).values(**kwargs).returning(model)
                )
                instances = result.scalars().all()
                logger.debug(f"Updated {len(instances)} {model.__name__} records by {field}={value}")
                return instances
            except Exception as e:
                logger.error(f"Failed to update {model.__name__} by {field}={value}: {e}")
                raise
    
    async def delete(self, model: Type[T], id: int) -> bool:
        """Delete record by ID"""
        async with self.get_session() as session:
            try:
                result = await session.execute(delete(model).where(model.id == id))
                deleted = result.rowcount > 0
                if deleted:
                    logger.debug(f"Deleted {model.__name__} {id}")
                return deleted
            except Exception as e:
                logger.error(f"Failed to delete {model.__name__} {id}: {e}")
                raise
    
    async def delete_by_field(self, model: Type[T],
                             field: str, value: Any) -> int:
        """Delete records by field value"""
        async with self.get_session() as session:
            try:
                result = await session.execute(delete(model).where(getattr(model, field) == value))
                deleted_count = result.rowcount
                logger.debug(f"Deleted {deleted_count} {model.__name__} records by {field}={value}")
                return deleted_count
            except Exception as e:
                logger.error(f"Failed to delete {model.__name__} by {field}={value}: {e}")
                raise
    
    async def count(self, model: Type[T],
                   filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filters"""
        async with self.get_session() as session:
            try:
                query = select(func.count(model.id))
                
                if filters:
                    for field, value in filters.items():
                        if hasattr(model, field):
                            query = query.where(getattr(model, field) == value)
                
                result = await session.execute(query)
                return result.scalar()
            except Exception as e:
                logger.error(f"Failed to count {model.__name__}: {e}")
                raise
    
    async def exists(self, model: Type[T],
                    field: str, value: Any) -> bool:
        """Check if record exists"""
        async with self.get_session() as session:
            try:
                result = await session.execute(
                    select(func.count(model.id)).where(getattr(model, field) == value)
                )
                return result.scalar() > 0
            except Exception as e:
                logger.error(f"Failed to check existence of {model.__name__} by {field}={value}: {e}")
                raise

# User-specific operations
class UserRepository:
    """Repository for user operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    async def create_user(self, telegram_id: int, status: str = "active") -> User:
        """Create new user"""
        return await self.db.create(User, telegram_id=telegram_id, status=status)
    
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID"""
        return await self.db.get_by_field(User, "telegram_id", telegram_id)
    
    async def get_user_with_subscriptions(self, telegram_id: int) -> Optional[User]:
        """Get user with their subscriptions"""
        async with self.db.get_session() as session:
            try:
                result = await session.execute(
                    select(User)
                    .options(selectinload(User.subscriptions))
                    .where(User.telegram_id == telegram_id)
                )
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Failed to get user with subscriptions: {e}")
                raise
    
    async def update_user_status(self, telegram_id: int, status: str) -> bool:
        """Update user status"""
        updated = await self.db.update_by_field(User, "telegram_id", telegram_id, status=status)
        return len(updated) > 0
    
    async def get_all_users(self, active_only: bool = False) -> List[User]:
        """Get all users"""
        filters = {"status": "active"} if active_only else None
        return await self.db.get_all(User, filters=filters)
    
    async def count_users(self, active_only: bool = False) -> int:
        """Count users"""
        filters = {"status": "active"} if active_only else None
        return await self.db.count(User, filters=filters)

# Subscription-specific operations
class SubscriptionRepository:
    """Repository for subscription operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    async def create_subscription(self, user_id: int, plan_name: str, price: float,
                                 duration_days: int, protocol: str) -> Subscription:
        """Create new subscription"""
        return await self.db.create(
            Subscription,
            user_id=user_id,
            plan_name=plan_name,
            price=price,
            duration_days=duration_days,
            protocol=protocol,
            status="pending"
        )
    
    async def get_user_subscriptions(self, user_id: int, active_only: bool = False) -> List[Subscription]:
        """Get user subscriptions"""
        filters = {"user_id": user_id}
        if active_only:
            filters["status"] = "active"
        return await self.db.get_all(Subscription, filters=filters, order_by="created_at")
    
    async def get_active_subscription(self, user_id: int) -> Optional[Subscription]:
        """Get user's active subscription"""
        async with self.db.get_session() as session:
            try:
                result = await session.execute(
                    select(Subscription)
                    .where(and_(
                        Subscription.user_id == user_id,
                        Subscription.status == "active"
                    ))
                    .order_by(Subscription.created_at.desc())
                )
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Failed to get active subscription: {e}")
                raise
    
    async def update_subscription_status(self, subscription_id: int, status: str) -> bool:
        """Update subscription status"""
        updated = await self.db.update(Subscription, subscription_id, status=status)
        return updated is not None
    
    async def get_expiring_subscriptions(self, days_ahead: int = 3) -> List[Subscription]:
        """Get subscriptions expiring soon"""
        from datetime import datetime, timedelta
        
        async with self.db.get_session() as session:
            try:
                expiry_date = datetime.now() + timedelta(days=days_ahead)
                result = await session.execute(
                    select(Subscription)
                    .options(selectinload(Subscription.user))
                    .where(and_(
                        Subscription.status == "active",
                        Subscription.expires_at <= expiry_date,
                        Subscription.expires_at > datetime.now()
                    ))
                )
                return result.scalars().all()
            except Exception as e:
                logger.error(f"Failed to get expiring subscriptions: {e}")
                raise

# Payment-specific operations
class PaymentRepository:
    """Repository for payment operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    async def create_payment(self, user_id: int, subscription_id: int,
                           amount: float, payment_method: str) -> Payment:
        """Create new payment"""
        return await self.db.create(
            Payment,
            user_id=user_id,
            subscription_id=subscription_id,
            amount=amount,
            payment_method=payment_method,
            status="pending"
        )
    
    async def get_payment_by_invoice_id(self, invoice_id: str) -> Optional[Payment]:
        """Get payment by invoice ID"""
        return await self.db.get_by_field(Payment, "payment_id", invoice_id)
    
    async def update_payment_status(self, payment_id: int, status: str,
                                  invoice_id: Optional[str] = None) -> bool:
        """Update payment status"""
        update_data = {"status": status}
        if invoice_id:
            update_data["payment_id"] = invoice_id
        if status == "completed":
            from datetime import datetime
            update_data["completed_at"] = datetime.now()
        
        updated = await self.db.update(Payment, payment_id, **update_data)
        return updated is not None
    
    async def get_user_payments(self, user_id: int) -> List[Payment]:
        """Get user payments"""
        return await self.db.get_all(Payment, filters={"user_id": user_id}, order_by="created_at")
    
    async def get_pending_payments(self) -> List[Payment]:
        """Get all pending payments"""
        return await self.db.get_all(Payment, filters={"status": "pending"})

# Notification-specific operations
class NotificationRepository:
    """Repository for notification operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    async def create_notification(self, user_id: int, notification_type: str,
                                 message: str, success: bool = True,
                                 error_message: Optional[str] = None) -> NotificationLog:
        """Create notification log"""
        return await self.db.create(
            NotificationLog,
            user_id=user_id,
            notification_type=notification_type,
            message=message,
            success=success,
            error_message=error_message
        )
    
    async def get_user_notifications(self, user_id: int, limit: int = 50) -> List[NotificationLog]:
        """Get user notifications"""
        return await self.db.get_all(
            NotificationLog,
            filters={"user_id": user_id},
            limit=limit,
            order_by="created_at"
        )

# Main database manager instance
db_manager = DatabaseManager()

# Repository instances
user_repo = UserRepository(db_manager)
subscription_repo = SubscriptionRepository(db_manager)
payment_repo = PaymentRepository(db_manager)
notification_repo = NotificationRepository(db_manager)

# Context manager for backward compatibility
@asynccontextmanager
async def get_db_context():
    """Backward compatibility context manager"""
    async with db_manager.get_session() as session:
        yield session

# Initialize function
async def init_db():
    """Initialize database and create tables"""
    await db_manager.initialize()
    
    # Create tables if they don't exist
    async with db_manager.get_session() as session:
        # Import all models to ensure they're registered
        from src.models import User, Subscription, Payment, NotificationLog, AdminAction
        
        # Create all tables
        async with db_manager._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database initialized successfully")
