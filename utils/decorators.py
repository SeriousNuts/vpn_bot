"""
Decorators for VPN Bot
"""

import functools
import logging
from typing import Callable, Any
from aiogram.types import Message, CallbackQuery
from src.core.config import settings

logger = logging.getLogger(__name__)

def admin_required(func: Callable) -> Callable:
    """
    Decorator to require admin access
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Try to get user_id from different argument types
        user_id = None
        
        for arg in args:
            if isinstance(arg, Message):
                user_id = arg.from_user.id
                break
            elif isinstance(arg, CallbackQuery):
                user_id = arg.from_user.id
                break
        
        if user_id is None:
            logger.error("Could not determine user_id in admin_required decorator")
            return None
        
        if user_id != settings.admin_id:
            logger.warning(f"Unauthorized admin access attempt by user {user_id}")
            return None
        
        return await func(*args, **kwargs)
    
    return wrapper

def log_errors(func: Callable) -> Callable:
    """
    Decorator to log function errors
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            raise
    return wrapper

def user_required(func: Callable) -> Callable:
    """
    Decorator to require user to exist in database
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        from src.core.database import get_db_context
        from src.models import User
        
        # Try to get user_id from different argument types
        user_id = None
        
        for arg in args:
            if isinstance(arg, Message):
                user_id = arg.from_user.id
                break
            elif isinstance(arg, CallbackQuery):
                user_id = arg.from_user.id
                break
        
        if user_id is None:
            logger.error("Could not determine user_id in user_required decorator")
            return None
        
        # Check if user exists
        async with get_db_context() as db:
            user = await db.get(User, user_id)
            if not user:
                logger.warning(f"User {user_id} not found in database")
                return None
        
        return await func(*args, **kwargs)
    
    return wrapper

def active_subscription_required(func: Callable) -> Callable:
    """
    Decorator to require user to have active subscription
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        from src.core.database import get_db_context
        from src.models import User, Subscription
        from src.enums import SubscriptionStatus
        
        # Try to get user_id from different argument types
        user_id = None
        
        for arg in args:
            if isinstance(arg, Message):
                user_id = arg.from_user.id
                break
            elif isinstance(arg, CallbackQuery):
                user_id = arg.from_user.id
                break
        
        if user_id is None:
            logger.error("Could not determine user_id in active_subscription_required decorator")
            return None
        
        # Check if user has active subscription
        async with get_db_context() as db:
            user = await db.get(User, user_id)
            if not user:
                return None
            
            # Find active subscription
            active_sub = None
            for sub in user.subscriptions:
                if sub.status == SubscriptionStatus.ACTIVE:
                    active_sub = sub
                    break
            
            if not active_sub:
                logger.info(f"User {user_id} has no active subscription")
                return None
        
        return await func(*args, **kwargs)
    
    return wrapper

def rate_limit(max_calls: int = 5, time_window: int = 60):
    """
    Decorator for rate limiting
    
    Args:
        max_calls: Maximum number of calls allowed
        time_window: Time window in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        # Simple in-memory rate limiting (not suitable for distributed systems)
        call_counts = {}
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Try to get user_id from different argument types
            user_id = None
            
            for arg in args:
                if isinstance(arg, Message):
                    user_id = arg.from_user.id
                    break
                elif isinstance(arg, CallbackQuery):
                    user_id = arg.from_user.id
                    break
            
            if user_id is None:
                return await func(*args, **kwargs)
            
            # Check rate limit
            import time
            current_time = time.time()
            
            if user_id not in call_counts:
                call_counts[user_id] = []
            
            # Remove old calls outside time window
            call_counts[user_id] = [
                call_time for call_time in call_counts[user_id]
                if current_time - call_time < time_window
            ]
            
            # Check if limit exceeded
            if len(call_counts[user_id]) >= max_calls:
                logger.warning(f"Rate limit exceeded for user {user_id}")
                return None
            
            # Add current call
            call_counts[user_id].append(current_time)
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator

def validate_state(state_name: str):
    """
    Decorator to validate FSM state
    
    Args:
        state_name: Expected state name
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            from aiogram.fsm.context import FSMContext
            
            # Find FSMContext in arguments
            state_context = None
            for arg in args:
                if isinstance(arg, FSMContext):
                    state_context = arg
                    break
            
            if not state_context:
                logger.error("FSMContext not found in arguments")
                return None
            
            current_state = await state_context.get_state()
            if current_state != state_name:
                logger.warning(f"Invalid state. Expected: {state_name}, Got: {current_state}")
                return None
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator

def cache_result(ttl: int = 300):
    """
    Simple in-memory cache decorator
    
    Args:
        ttl: Time to live in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        cache = {}
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            import time
            import hashlib
            
            # Create cache key
            key_data = str(args) + str(sorted(kwargs.items()))
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Check cache
            if cache_key in cache:
                cached_time, result = cache[cache_key]
                if time.time() - cached_time < ttl:
                    return result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache[cache_key] = (time.time(), result)
            
            return result
        
        return wrapper
    
    return decorator
