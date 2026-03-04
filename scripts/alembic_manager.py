#!/usr/bin/env python3
"""
Alembic migration manager for VPN Bot
"""

import asyncio
import sys
import os
from typing import Optional

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from alembic.config import Config
from alembic import command
from src.core.config import settings

class AlembicManager:
    """Manager for Alembic migrations"""
    
    def __init__(self):
        self.alembic_cfg = Config("alembic.ini")
        self.alembic_cfg.set_main_option("sqlalchemy.url", settings.alembic_url)
    
    def upgrade(self, revision: str = "head") -> bool:
        """Upgrade to specific revision"""
        try:
            command.upgrade(self.alembic_cfg, revision)
            print(f"✅ Successfully upgraded to revision: {revision}")
            return True
        except Exception as e:
            print(f"❌ Upgrade failed: {str(e)}")
            return False
    
    def downgrade(self, revision: str) -> bool:
        """Downgrade to specific revision"""
        try:
            command.downgrade(self.alembic_cfg, revision)
            print(f"✅ Successfully downgraded to revision: {revision}")
            return True
        except Exception as e:
            print(f"❌ Downgrade failed: {str(e)}")
            return False
    
    def current(self) -> Optional[str]:
        """Get current revision"""
        try:
            current_rev = command.current(self.alembic_cfg)
            print(f"📍 Current revision: {current_rev}")
            return current_rev
        except Exception as e:
            print(f"❌ Failed to get current revision: {str(e)}")
            return None
    
    def history(self) -> bool:
        """Show migration history"""
        try:
            command.history(self.alembic_cfg)
            return True
        except Exception as e:
            print(f"❌ Failed to show history: {str(e)}")
            return False
    
    def heads(self) -> bool:
        """Show available heads"""
        try:
            command.heads(self.alembic_cfg)
            return True
        except Exception as e:
            print(f"❌ Failed to show heads: {str(e)}")
            return False
    
    def revision(self, message: Optional[str] = None, autogenerate: bool = False) -> bool:
        """Create new revision"""
        try:
            command.revision(
                self.alembic_cfg,
                message=message,
                autogenerate=autogenerate
            )
            print("✅ New revision created successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to create revision: {str(e)}")
            return False
    
    def stamp(self, revision: str) -> bool:
        """Stamp database with revision without running migrations"""
        try:
            command.stamp(self.alembic_cfg, revision)
            print(f"✅ Database stamped with revision: {revision}")
            return True
        except Exception as e:
            print(f"❌ Failed to stamp database: {str(e)}")
            return False

def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("Usage: python alembic_manager.py <command> [args]")
        print("Commands:")
        print("  upgrade [revision]  - Upgrade to revision (default: head)")
        print("  downgrade <revision> - Downgrade to revision")
        print("  current            - Show current revision")
        print("  history            - Show migration history")
        print("  heads              - Show available heads")
        print("  revision [message]  - Create new revision")
        print("  autogenerate [msg]  - Create new revision with autogenerate")
        print("  stamp <revision>    - Stamp database with revision")
        sys.exit(1)
    
    manager = AlembicManager()
    cmd = sys.argv[1].lower()
    
    if cmd == "upgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "head"
        success = manager.upgrade(revision)
    elif cmd == "downgrade":
        if len(sys.argv) < 3:
            print("❌ Revision required for downgrade")
            sys.exit(1)
        revision = sys.argv[2]
        success = manager.downgrade(revision)
    elif cmd == "current":
        success = manager.current() is not None
    elif cmd == "history":
        success = manager.history()
    elif cmd == "heads":
        success = manager.heads()
    elif cmd == "revision":
        message = sys.argv[2] if len(sys.argv) > 2 else None
        success = manager.revision(message)
    elif cmd == "autogenerate":
        message = sys.argv[2] if len(sys.argv) > 2 else None
        success = manager.revision(message, autogenerate=True)
    elif cmd == "stamp":
        if len(sys.argv) < 3:
            print("❌ Revision required for stamp")
            sys.exit(1)
        revision = sys.argv[2]
        success = manager.stamp(revision)
    else:
        print(f"❌ Unknown command: {cmd}")
        sys.exit(1)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
