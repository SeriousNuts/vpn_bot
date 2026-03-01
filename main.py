#!/usr/bin/env python3
"""
VPN Bot - Main entry point
"""

import asyncio

from src.bot import main
from utils.logger import setup_logging



async def run_async_tasks():
    vpn_bot = asyncio.create_task(main())
    await asyncio.gather(vpn_bot)

if __name__ == "__main__":
    # Configure logging
    setup_logging()
    
    # Run the bot
    asyncio.run(run_async_tasks())
