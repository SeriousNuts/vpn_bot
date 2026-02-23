"""
Validation utilities for VPN Bot
"""

import re
from typing import Optional, List
from datetime import datetime

class ValidationError(Exception):
    """Custom validation error"""
    pass

def validate_email(email: str) -> bool:
    """
    Validate email address format
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_phone(phone: str) -> bool:
    """
    Validate phone number format
    
    Args:
        phone: Phone number to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    return len(digits_only) >= 10 and len(digits_only) <= 15

def validate_username(username: str) -> bool:
    """
    Validate Telegram username format
    
    Args:
        username: Username to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not username:
        return True  # Username is optional
    
    # Remove @ if present
    clean_username = username.lstrip('@')
    
    # Telegram username rules: 5-32 characters, letters, numbers, underscores
    pattern = r'^[a-zA-Z0-9_]{5,32}$'
    return bool(re.match(pattern, clean_username))

def validate_plan_name(plan: str) -> bool:
    """
    Validate subscription plan name
    
    Args:
        plan: Plan name to validate
        
    Returns:
        True if valid, False otherwise
    """
    valid_plans = ["1_month", "3_months", "6_months", "1_year"]
    return plan in valid_plans

def validate_protocol(protocol: str) -> bool:
    """
    Validate VPN protocol
    
    Args:
        protocol: Protocol to validate
        
    Returns:
        True if valid, False otherwise
    """
    from src.enums import ProtocolType
    return protocol in [p.value for p in ProtocolType]

def validate_amount(amount: float) -> bool:
    """
    Validate payment amount
    
    Args:
        amount: Amount to validate
        
    Returns:
        True if valid, False otherwise
    """
    return amount > 0 and amount <= 10000  # Max $10,000

def validate_telegram_id(telegram_id: int) -> bool:
    """
    Validate Telegram user ID
    
    Args:
        telegram_id: Telegram ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    return telegram_id > 0 and telegram_id < 2**31  # Within Telegram ID range

def validate_date_range(start_date: Optional[datetime], end_date: Optional[datetime]) -> bool:
    """
    Validate date range
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        True if valid, False otherwise
    """
    if start_date and end_date:
        return start_date < end_date
    return True

def validate_subscription_data(data: dict) -> List[str]:
    """
    Validate subscription data
    
    Args:
        data: Subscription data dictionary
        
    Returns:
        List of validation errors
    """
    errors = []
    
    # Validate required fields
    required_fields = ['user_id', 'plan_name', 'price', 'duration_days', 'protocol']
    for field in required_fields:
        if field not in data or data[field] is None:
            errors.append(f"Missing required field: {field}")
    
    # Validate specific fields
    if 'plan_name' in data and not validate_plan_name(data['plan_name']):
        errors.append("Invalid plan name")
    
    if 'protocol' in data and not validate_protocol(data['protocol']):
        errors.append("Invalid protocol")
    
    if 'price' in data and not validate_amount(data['price']):
        errors.append("Invalid price amount")
    
    if 'duration_days' in data and (data['duration_days'] <= 0 or data['duration_days'] > 3650):
        errors.append("Invalid duration (must be 1-3650 days)")
    
    return errors

def validate_payment_data(data: dict) -> List[str]:
    """
    Validate payment data
    
    Args:
        data: Payment data dictionary
        
    Returns:
        List of validation errors
    """
    errors = []
    
    # Validate required fields
    required_fields = ['user_id', 'amount', 'payment_method']
    for field in required_fields:
        if field not in data or data[field] is None:
            errors.append(f"Missing required field: {field}")
    
    # Validate specific fields
    if 'amount' in data and not validate_amount(data['amount']):
        errors.append("Invalid amount")
    
    if 'payment_method' in data and data['payment_method'] not in ['cryptobot']:
        errors.append("Invalid payment method")
    
    return errors

def sanitize_string(text: str, max_length: int = 255) -> str:
    """
    Sanitize string input
    
    Args:
        text: Text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not text:
        return ""
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\']', '', text)
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized.strip()

def validate_config() -> List[str]:
    """
    Validate application configuration
    
    Returns:
        List of configuration errors
    """
    errors = []
    
    from src.core.config import settings
    
    # Validate required settings
    if not settings.bot_token:
        errors.append("BOT_TOKEN is required")
    
    if not settings.admin_id:
        errors.append("ADMIN_ID is required")
    
    if not settings.database_url:
        errors.append("DATABASE_URL is required")
    
    if not settings.marzban_url:
        errors.append("MARZBAN_URL is required")
    
    if not settings.cryptobot_token:
        errors.append("CRYPTOBOT_TOKEN is required")
    
    # Validate formats
    if settings.bot_token and not settings.bot_token.startswith(':'):
        errors.append("Invalid BOT_TOKEN format")
    
    if settings.admin_id and not validate_telegram_id(settings.admin_id):
        errors.append("Invalid ADMIN_ID")
    
    if settings.support_username and not validate_username(settings.support_username):
        errors.append("Invalid SUPPORT_USERNAME")
    
    return errors
