"""
Helper functions for VPN Bot
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional

def generate_username(prefix: str = "user") -> str:
    """Generate a random username"""
    return f"{prefix}_{secrets.token_hex(4)}"

def generate_password(length: int = 12) -> str:
    """Generate a random password"""
    return secrets.token_urlsafe(length)

def generate_uuid() -> str:
    """Generate a UUID for VPN configurations"""
    return secrets.token_hex(16)

def format_date(date: datetime, format_str: str = "%Y-%m-%d %H:%M") -> str:
    """Format datetime to string"""
    if not date:
        return "N/A"
    return date.strftime(format_str)

def calculate_remaining_days(expires_at: datetime) -> int:
    """Calculate remaining days until expiry"""
    if not expires_at:
        return 0
    delta = expires_at - datetime.now()
    return max(0, delta.days)

def validate_email(email: str) -> bool:
    """Basic email validation"""
    return "@" in email and "." in email and len(email) > 5

def validate_phone(phone: str) -> bool:
    """Basic phone validation"""
    return phone.isdigit() and len(phone) >= 10

def mask_string(s: str, visible_chars: int = 4) -> str:
    """Mask a string showing only first and last few characters"""
    if len(s) <= visible_chars * 2:
        return s
    return s[:visible_chars] + "*" * (len(s) - visible_chars * 2) + s[-visible_chars:]

def format_price(amount: float, currency: str = "USD") -> str:
    """Format price with currency"""
    return f"{currency} {amount:.2f}"

def get_duration_days(plan: str) -> int:
    """Get duration in days for a plan"""
    durations = {
        "1_month": 30,
        "3_months": 90,
        "6_months": 180,
        "1_year": 365
    }
    return durations.get(plan, 30)

def format_plan_name(plan: str) -> str:
    """Format plan name for display"""
    return plan.replace("_", " ").title()

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to maximum length"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    from src.core.config import settings
    return user_id == settings.admin_id

def get_status_emoji(status: str) -> str:
    """Get emoji for status"""
    status_emojis = {
        "active": "🟢",
        "inactive": "🟡", 
        "banned": "🔴",
        "pending": "⏳",
        "completed": "✅",
        "failed": "❌",
        "expired": "⏰"
    }
    return status_emojis.get(status.lower(), "❓")

def create_backup_filename(prefix: str = "backup") -> str:
    """Create backup filename with timestamp"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.sql"
