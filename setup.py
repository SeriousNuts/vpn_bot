#!/usr/bin/env python3
"""
Setup script for VPN Bot
"""

import asyncio
from src.core.database import init_db

async def setup():
    """Initialize database and create tables"""
    print("Initializing database...")
    await init_db()
    print("Database initialized successfully!")
    print("Bot is ready to run!")

if __name__ == "__main__":
    asyncio.run(setup())
