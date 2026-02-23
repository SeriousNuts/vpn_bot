#!/usr/bin/env python3
"""
Script to backup database
"""

import asyncio
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from src.core.config import settings

async def backup_database():
    """Create database backup"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_{timestamp}.sql"
    
    print(f"Creating database backup: {backup_file}")
    
    try:
        # Extract database connection info
        db_url = settings.database_url
        if "postgresql+asyncpg://" in db_url:
            # Convert to regular postgresql URL for pg_dump
            pg_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
            
            # Parse connection details
            # Format: postgresql://username:password@host:port/database
            parts = pg_url.replace("postgresql://", "").split("/")
            conn_part = parts[0]
            db_name = parts[1] if len(parts) > 1 else "vpn_bot"
            
            if "@" in conn_part:
                auth_part, host_port = conn_part.split("@")
                username, password = auth_part.split(":")
                
                if ":" in host_port:
                    host, port = host_port.split(":")
                else:
                    host = host_port
                    port = "5432"
            else:
                print("Error: Invalid database URL format")
                return
            
            # Create pg_dump command
            cmd = [
                "pg_dump",
                "-h", host,
                "-p", port,
                "-U", username,
                "-d", db_name,
                "-f", backup_file,
                "--verbose",
                "--no-password"
            ]
            
            # Set password environment variable
            env = subprocess.environ.copy()
            env["PGPASSWORD"] = password
            
            # Run backup
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Backup created successfully: {backup_file}")
                print(f"📁 File size: {Path(backup_file).stat().st_size / 1024 / 1024:.2f} MB")
            else:
                print(f"❌ Backup failed: {result.stderr}")
                
        else:
            print("Error: Only PostgreSQL is supported for backup")
            
    except Exception as e:
        print(f"❌ Backup error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(backup_database())
