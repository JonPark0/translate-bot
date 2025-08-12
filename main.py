#!/usr/bin/env python3

import os
import asyncio
import logging
import signal
import sys
from typing import Dict, Optional
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from bot.translation_bot import TranslationBot
from bot.health_server import HealthServer
from utils.logger import setup_logger
from utils.rate_limiter import RateLimiter
from utils.cost_monitor import CostMonitor


async def main():
    load_dotenv()
    
    logger = setup_logger()
    
    required_env_vars = [
        'DISCORD_TOKEN',
        'GEMINI_API_KEY',
        'SERVER_ID',
        'KOREAN_CHANNEL_ID',
        'ENGLISH_CHANNEL_ID',
        'JAPANESE_CHANNEL_ID',
        'CHINESE_CHANNEL_ID'
    ]
    
    for var in required_env_vars:
        if not os.getenv(var):
            logger.critical(f"Missing required environment variable: {var} - Bot cannot start")
            sys.exit(1)
    
    logger.info("Starting Key Translation Bot...")
    
    rate_limiter = RateLimiter(
        requests_per_minute=int(os.getenv('RATE_LIMIT_PER_MINUTE', 30)),
        max_daily_requests=int(os.getenv('MAX_DAILY_REQUESTS', 1000))
    )
    
    cost_monitor = CostMonitor(
        max_monthly_cost=float(os.getenv('MAX_MONTHLY_COST_USD', 10.0)),
        alert_threshold=float(os.getenv('COST_ALERT_THRESHOLD_USD', 8.0))
    )
    
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    
    bot = TranslationBot(
        command_prefix='!',
        intents=intents,
        rate_limiter=rate_limiter,
        cost_monitor=cost_monitor
    )
    
    health_server = HealthServer(bot)
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}. Shutting down gracefully...")
        asyncio.create_task(shutdown(bot, health_server))
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        await asyncio.gather(
            bot.start(os.getenv('DISCORD_TOKEN')),
            health_server.start()
        )
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)
    finally:
        await shutdown(bot, health_server)


async def shutdown(bot: TranslationBot, health_server: HealthServer):
    logger = logging.getLogger(__name__)
    logger.info("Shutting down bot...")
    
    try:
        await health_server.stop()
        await bot.close()
        logger.info("Bot shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)