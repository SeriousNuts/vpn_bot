import logging
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from src.core.config import settings
from src.core.database import init_db
from src.handlers.admin import admin_router
from src.handlers.user import user_router
from src.handlers.user_updated import user_router as user_updated_router
from src.services.notification import NotificationService



# Initialize bot
bot_instance: Optional[Bot] = None

def set_bot(bot: Bot):
    global bot_instance
    bot_instance = bot

def get_bot() -> Bot:
    if bot_instance is None:
        raise RuntimeError("Bot not initialized")
    return bot_instance

def init_bot():
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher(storage=MemoryStorage())
    return bot, dp

async def set_webhook(bot: Bot, webhook_url: str):
    """Установка webhook URL"""
    await bot.set_webhook(webhook_url)


async def delete_webhook(bot: Bot):
    """Удаление webhook (для переключения на polling)"""
    await bot.delete_webhook()


async def main() -> None:
    """Main function to start the bot"""
    logging.info(f"Starting bot...")
    if settings.init_db:
        await init_db()
        logging.info("Database initialized")
    """Запуск бота в режиме webhook"""
    bot, dp = init_bot()
    # Include routers
    #dp.include_router(user_router)
    dp.include_router(user_updated_router)
    dp.include_router(admin_router)

    await delete_webhook(bot)
    set_bot(bot)
    logging.info("===telegram bot started in POLLING mode===")
    await dp.start_polling(bot, skip_updates=False)

    notification_service = NotificationService()
    await notification_service.start()
    logging.info("Notification service started")
