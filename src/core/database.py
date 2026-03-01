"""
Database module - backward compatibility wrapper
"""

from .database_manager import (
    db_manager,
    user_repo,
    subscription_repo,
    payment_repo,
    notification_repo,
    get_db_context,
    init_db
)

# Re-export for backward compatibility
__all__ = [
    'db_manager',
    'user_repo',
    'subscription_repo', 
    'payment_repo',
    'notification_repo',
    'get_db_context',
    'init_db'
]
