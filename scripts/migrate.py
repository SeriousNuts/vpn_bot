#!/usr/bin/env python3
"""
Script to run database migrations
"""

import asyncio
import sys
from alembic.config import Config
from alembic import command
from src.core.config import settings

async def run_migrations():
    """Run database migrations"""
    print("Running database migrations...")
    
    try:
        # Configure Alembic
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
        
        # Run migrations
        command.upgrade(alembic_cfg, "head")
        print("✅ Migrations completed successfully")
        
    except Exception as e:
        print(f"❌ Migration error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_migrations())
