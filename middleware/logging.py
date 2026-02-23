"""
Logging middleware for VPN Bot
"""

import logging
import time
from typing import Callable, Any, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update
from src.core.config import settings

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseMiddleware):
    """
    Middleware for logging all bot interactions
    """
    
    async def __call__(
        self,
        handler: Callable,
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        start_time = time.time()
        
        # Log incoming update
        user_info = self._get_user_info(event)
        update_info = self._get_update_info(event)
        
        logger.info(f"Received update: {update_info} from {user_info}")
        
        try:
            # Execute handler
            result = await handler(event, data)
            
            # Log execution time
            execution_time = time.time() - start_time
            logger.info(f"Update processed successfully in {execution_time:.3f}s")
            
            return result
            
        except Exception as e:
            # Log error
            execution_time = time.time() - start_time
            logger.error(
                f"Update processing failed in {execution_time:.3f}s: {str(e)}",
                exc_info=True,
                extra={
                    'user_info': user_info,
                    'update_info': update_info,
                    'execution_time': execution_time
                }
            )
            raise
    
    def _get_user_info(self, event: Update) -> str:
        """Extract user information from update"""
        if event.message:
            user = event.message.from_user
        elif event.callback_query:
            user = event.callback_query.from_user
        elif event.inline_query:
            user = event.inline_query.from_user
        else:
            return "Unknown user"
        
        return f"ID:{user.id} Username:@{user.username} Name:{user.full_name}"
    
    def _get_update_info(self, event: Update) -> str:
        """Extract update information"""
        if event.message:
            return f"Message: {event.message.text[:50]}..." if event.message.text else f"Message: {event.message.content_type}"
        elif event.callback_query:
            return f"Callback: {event.callback_query.data}"
        elif event.inline_query:
            return f"Inline: {event.inline_query.query[:50]}..."
        else:
            return f"Update type: {event.event_type}"

class ErrorLoggingMiddleware(BaseMiddleware):
    """
    Middleware specifically for error logging and user notifications
    """
    
    async def __call__(
        self,
        handler: Callable,
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            # Log detailed error information
            user_info = self._get_user_info(event)
            logger.error(
                f"Unhandled error for {user_info}: {str(e)}",
                exc_info=True,
                extra={
                    'user_info': user_info,
                    'event_data': event.model_dump() if event else None
                }
            )
            
            # Try to notify user about error
            await self._notify_user_about_error(event)
            
            # Re-raise the exception
            raise
    
    def _get_user_info(self, event: Update) -> str:
        """Extract user information from update"""
        if event.message:
            user = event.message.from_user
        elif event.callback_query:
            user = event.callback_query.from_user
        else:
            return "Unknown user"
        
        return f"ID:{user.id} Username:@{user.username}"
    
    async def _notify_user_about_error(self, event: Update):
        """Try to notify user about the error"""
        try:
            from src.bot import bot
            
            if event.message:
                await bot.send_message(
                    event.message.chat.id,
                    "❌ An error occurred while processing your request. Please try again later."
                )
            elif event.callback_query:
                await bot.answer_callback_query(
                    event.callback_query.id,
                    "❌ An error occurred. Please try again later.",
                    show_alert=True
                )
        except Exception as notify_error:
            logger.error(f"Failed to notify user about error: {str(notify_error)}")

class SecurityMiddleware(BaseMiddleware):
    """
    Middleware for security checks and rate limiting
    """
    
    def __init__(self):
        self.request_counts = {}
        self.blocked_users = set()
    
    async def __call__(
        self,
        handler: Callable,
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        user_id = self._get_user_id(event)
        
        if not user_id:
            return await handler(event, data)
        
        # Check if user is blocked
        if user_id in self.blocked_users:
            logger.warning(f"Blocked user {user_id} attempted to access bot")
            return None
        
        # Simple rate limiting
        if not self._check_rate_limit(user_id):
            logger.warning(f"Rate limit exceeded for user {user_id}")
            return None
        
        # Log security events
        await self._log_security_event(event, user_id)
        
        return await handler(event, data)
    
    def _get_user_id(self, event: Update) -> int:
        """Extract user ID from update"""
        if event.message:
            return event.message.from_user.id
        elif event.callback_query:
            return event.callback_query.from_user.id
        elif event.inline_query:
            return event.inline_query.from_user.id
        return None
    
    def _check_rate_limit(self, user_id: int, max_requests: int = 30, time_window: int = 60) -> bool:
        """Simple rate limiting check"""
        import time
        
        current_time = time.time()
        
        if user_id not in self.request_counts:
            self.request_counts[user_id] = []
        
        # Remove old requests outside time window
        self.request_counts[user_id] = [
            req_time for req_time in self.request_counts[user_id]
            if current_time - req_time < time_window
        ]
        
        # Check if limit exceeded
        if len(self.request_counts[user_id]) >= max_requests:
            return False
        
        # Add current request
        self.request_counts[user_id].append(current_time)
        return True
    
    async def _log_security_event(self, event: Update, user_id: int):
        """Log security-related events"""
        # Check for suspicious patterns
        if event.message and event.message.text:
            text = event.message.text.lower()
            
            # Check for potential attacks
            suspicious_patterns = [
                'drop table',
                'select *',
                'union select',
                'script>',
                'javascript:',
                '<iframe',
                'eval(',
                'exec('
            ]
            
            for pattern in suspicious_patterns:
                if pattern in text:
                    logger.warning(f"Suspicious pattern detected from user {user_id}: {pattern}")
                    break
        
        # Log admin actions
        if user_id == settings.admin_id:
            logger.info(f"Admin action: {self._get_update_info(event)}")
    
    def _get_update_info(self, event: Update) -> str:
        """Extract update information"""
        if event.message:
            return f"Message: {event.message.text[:50]}..." if event.message.text else f"Message: {event.message.content_type}"
        elif event.callback_query:
            return f"Callback: {event.callback_query.data}"
        return f"Update type: {event.event_type}"
    
    def block_user(self, user_id: int):
        """Block a user from accessing the bot"""
        self.blocked_users.add(user_id)
        logger.info(f"User {user_id} has been blocked")
    
    def unblock_user(self, user_id: int):
        """Unblock a user"""
        self.blocked_users.discard(user_id)
        logger.info(f"User {user_id} has been unblocked")
