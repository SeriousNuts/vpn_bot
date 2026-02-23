#!/usr/bin/env python3
"""
VPN Bot - Main entry point
"""

import asyncio
import logging
from src.bot import main

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the bot
    asyncio.run(main())
