import asyncio
import logging
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from bot import dp
from src.core.config import settings
from src.core.database import init_db
from src.models import User
from src.enums.user import UserStatus
from src.services.notification import NotificationService
from src.handlers.user import user_router
from src.handlers.admin import admin_router
from src.core.database import get_db_context
from src.handlers.user import get_main_keyboard

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
storage = MemoryStorage()

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
    dp = Dispatcher()
    return bot, dp

async def set_webhook(bot: Bot, webhook_url: str):
    """Установка webhook URL"""
    await bot.set_webhook(webhook_url)


async def delete_webhook(bot: Bot):
    """Удаление webhook (для переключения на polling)"""
    await bot.delete_webhook()


@user_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command"""
    await state.clear()
    

    
    async with get_db_context() as db:
        user = await db.get(User, message.from_user.id)
        
        if not user:
            # Create new user
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                status=UserStatus.ACTIVE
            )
            db.add(user)
            await db.commit()
            
            welcome_text = (
                "🎉 Welcome to VPN Bot!\n\n"
                "To get started, please complete your registration:\n"
                "📱 Share your phone number\n"
                "📧 Provide your email\n\n"
                "Let's start with your phone number:"
            )
            
            from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
            keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="📱 Share Phone", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await message.answer(welcome_text, reply_markup=keyboard)
            from src.handlers.user import RegistrationStates
            await state.set_state(RegistrationStates.phone)
        else:
            # Existing user
            if message.from_user.id == settings.admin_id:
                from src.handlers.admin import get_admin_keyboard
                keyboard = get_admin_keyboard()
                await message.answer("👋 Welcome Admin!", reply_markup=keyboard)
            else:
                keyboard = get_main_keyboard(message.from_user.id)
                await message.answer("👋 Welcome back!", reply_markup=keyboard)



async def main() -> None:
    """Main function to start the bot"""
    await init_db()
    logger.info("Database initialized")
    """Запуск бота в режиме polling"""
    bot, dp = init_bot()
    # Include routers
    dp.include_router(user_router)
    dp.include_router(admin_router)

    await delete_webhook(bot)
    set_bot(bot)
    logging.info("===telegram bot started in POLLING mode===")
    await dp.start_polling(bot, skip_updates=False)

    notification_service = NotificationService()
    await notification_service.start()
    logger.info("Notification service started")

if __name__ == "__main__":
    asyncio.run(main())
