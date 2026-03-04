#!/usr/bin/env python3
"""
Script to run database migrations
"""

import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from alembic.config import Config
from alembic import command
from src.core.config import settings

async def run_migration():
    """Run database migration"""
    print("Running database migration...")
    
    try:
        # Configure Alembic
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", settings.alembic_url)
        
        # Run migration
        command.upgrade(alembic_cfg, "head")
        print("✅ Migration completed successfully")
        
    except Exception as e:
        print(f"❌ Migration error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_migration())
