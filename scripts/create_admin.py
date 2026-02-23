#!/usr/bin/env python3
"""
Script to create an admin user
"""

import asyncio
import sys
from src.core.database import get_db_context
from src.models import User
from src.enums import UserStatus

async def create_admin():
    """Create admin user"""
    if len(sys.argv) != 3:
        print("Usage: python create_admin.py <telegram_id> <username>")
        sys.exit(1)
    
    try:
        telegram_id = int(sys.argv[1])
        username = sys.argv[2]
    except ValueError:
        print("Error: Telegram ID must be a number")
        sys.exit(1)
    
    async with get_db_context() as db:
        # Check if user already exists
        existing_user = await db.get(User, telegram_id)
        if existing_user:
            print(f"User {telegram_id} already exists")
            return
        
        # Create admin user
        admin_user = User(
            telegram_id=telegram_id,
            username=username,
            first_name="Admin",
            status=UserStatus.ACTIVE
        )
        
        db.add(admin_user)
        await db.commit()
        
        print(f"Admin user created successfully:")
        print(f"  Telegram ID: {telegram_id}")
        print(f"  Username: @{username}")
        print(f"  Status: {admin_user.status}")

if __name__ == "__main__":
    asyncio.run(create_admin())
