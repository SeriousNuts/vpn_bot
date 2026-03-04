"""
Обновленные пользовательские хендлеры с интеграцией платежей через Telegram Stars
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.enums import ParseMode

from src.core.database import user_repo, subscription_repo
from src.models import User, Subscription
from src.enums import SubscriptionStatus
from src.services.marzban import marzban_service
from src.services.notification import NotificationService
from src.handlers.payment_integration import update_main_keyboard_with_payments
from utils.format_error import format_error_traceback

logger = logging.getLogger(__name__)

# Создаем роутер
user_router = Router()


async def get_back_to_main_inline_keyboard() -> InlineKeyboardMarkup:
    """
    Создание inline клавиатуры для возврата в главное меню
    
    Returns:
        InlineKeyboardMarkup с кнопкой возврата
    """
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="show_main_menu"
        )
    )
    return builder.as_markup()


async def get_main_keyboard(user_id: int):
    """
    Создание главной клавиатуры пользователя
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        ReplyKeyboardMarkup с главным меню
    """
    return await update_main_keyboard_with_payments()


@user_router.message(Command("start"))
async def cmd_start(message: Message):
    """
    Обработчик команды /start
    """
    try:
        # Получаем или создаем пользователя
        user = await user_repo.get_user_by_telegram_id(message.from_user.id)
        
        if not user:
            # Создаем нового пользователя
            user = await user_repo.create_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
            
            welcome_text = (
                "🎉 **Добро пожаловать в VPN Bot!**\n\n"
                "🚀 Я помогу вам получить доступ к безопасному и быстрому интернету.\n\n"
                "💡 **Что я могу делать:**\n"
                "• 📱 Управлять вашей VPN подпиской\n"
                "• 💎 Принимать оплату через Telegram Stars\n"
                "• 📊 Показывать статистику использования\n"
                "• 💬 Оказывать поддержку\n\n"
                "🎯 **Начните с выбора тарифа:**"
            )
        else:
            # Обновляем информацию о пользователе
            user.username = message.from_user.username
            user.first_name = message.from_user.first_name
            user.last_name = message.from_user.last_name
            await user_repo.update_user(user)
            
            welcome_text = (
                f"👋 **С возвращением, {user.first_name or 'пользователь'}!**\n\n"
                "🚀 Готов помочь вам с VPN подпиской.\n\n"
                "💡 **Доступные действия:**\n"
                "• 📱 Посмотреть текущую подписку\n"
                "• 💎 Купить новую подписку\n"
                "• 💳 История платежей\n"
                "• 📊 Статистика использования\n\n"
                "🎯 **Выберите действие:**"
            )
        
        # Создаем клавиатуру
        keyboard = await get_main_keyboard(message.from_user.id)
        
        await message.answer(
            welcome_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /start: {format_error_traceback(e)}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


@user_router.message(F.text == "🏠 Главное меню")
async def cmd_main_menu(message: Message):
    """
    Обработчик кнопки "Главное меню"
    """
    try:
        keyboard = await get_main_keyboard(message.from_user.id)
        
        await message.answer(
            "🏠 **Главное меню**\n\n"
            "Выберите действие:",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в главном меню: {format_error_traceback(e)}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


@user_router.message(F.text == "💎 Купить подписку")
async def cmd_buy_subscription(message: Message):
    """
    Обработчик кнопки "Купить подписку"
    """
    try:
        from src.handlers.payment_stars import cmd_buy_stars
        await cmd_buy_stars(message)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в покупке подписки: {format_error_traceback(e)}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


@user_router.message(F.text == "💳 История платежей")
async def cmd_payment_history(message: Message):
    """
    Обработчик кнопки "История платежей"
    """
    try:
        from src.handlers.payment_stars import cmd_payment_history
        await cmd_payment_history(message)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в истории платежей: {format_error_traceback(e)}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


@user_router.message(F.text == "📱 Моя подписка")
async def cmd_my_subscription(message: Message):
    """
    Обработчик кнопки "Моя подписка"
    """
    try:
        # Получаем пользователя
        user = await user_repo.get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer(
                "❌ Пользователь не найден. Используйте /start",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Получаем активную подписку
        subscription = await subscription_repo.get_active_subscription(user.id)
        
        if not subscription:
            text = (
                "📱 **Ваша подписка**\n\n"
                "❌ У вас нет активной подписки.\n\n"
                "💎 **Хотите оформить?**\n"
                "Нажмите кнопку \"💎 Купить подписку\" для выбора тарифа."
            )
        else:
            # Получаем информацию из Marzban
            if subscription.marzban_username:
                marzban_user = await marzban_service.get_user(subscription.marzban_username)
                
                if marzban_user:
                    # Формируем информацию о подписке
                    expire_date = datetime.fromtimestamp(marzban_user.expire)
                    used_gb = marzban_user.used_traffic / (1024**3)
                    limit_gb = marzban_user.data_limit / (1024**3) if marzban_user.data_limit > 0 else "∞"
                    
                    status_emoji = {
                        "active": "✅",
                        "disabled": "❌",
                        "limited": "⚠️",
                        "expired": "🕐"
                    }.get(marzban_user.status, "❓")
                    
                    text = (
                        f"📱 **Ваша подписка**\n\n"
                        f"{status_emoji} **Статус:** {marzban_user.status}\n"
                        f"📅 **Действительна до:** {expire_date.strftime('%Y-%m-%d %H:%M')}\n"
                        f"📊 **Трафик:** {used_gb:.2f}GB / {limit_gb}GB\n"
                        f"🌐 **Протокол:** {subscription.protocol}\n"
                        f"💰 **Тариф:** {subscription.plan_name}\n\n"
                    )
                    
                    if marzban_user.subscription_url:
                        text += f"🔗 **Подписка:** [получить конфигурацию]({marzban_user.subscription_url})"
                else:
                    # Если не удалось получить данные из Marzban
                    expire_date = subscription.expires_at
                    text = (
                        f"📱 **Ваша подписка**\n\n"
                        f"✅ **Статус:** Активна\n"
                        f"📅 **Действительна до:** {expire_date.strftime('%Y-%m-%d %H:%M')}\n"
                        f"🌐 **Протокол:** {subscription.protocol}\n"
                        f"💰 **Тариф:** {subscription.plan_name}\n\n"
                        f"⚠️ *Конфигурация временно недоступна. Попробуйте позже.*"
                    )
            else:
                # Если нет привязки к Marzban
                expire_date = subscription.expires_at
                text = (
                    f"📱 **Ваша подписка**\n\n"
                    f"✅ **Статус:** Активна\n"
                    f"📅 **Действительна до:** {expire_date.strftime('%Y-%m-%d %H:%M')}\n"
                    f"🌐 **Протокол:** {subscription.protocol}\n"
                    f"💰 **Тариф:** {subscription.plan_name}\n\n"
                    f"⚠️ *Конфигурация готовится...*"
                )
        
        keyboard = await get_main_keyboard(message.from_user.id)
        
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в моей подписке: {format_error_traceback(e)}")
        await message.answer(
            "❌ Произошла ошибка при загрузке подписки.",
            parse_mode=ParseMode.HTML
        )


@user_router.message(F.text == "📊 Статистика")
async def cmd_statistics(message: Message):
    """
    Обработчик кнопки "Статистика"
    """
    try:
        # Получаем пользователя
        user = await user_repo.get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer(
                "❌ Пользователь не найден. Используйте /start",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Получаем активную подписку
        subscription = await subscription_repo.get_active_subscription(user.id)
        
        if not subscription:
            text = (
                "📊 **Статистика**\n\n"
                "❌ У вас нет активной подписки.\n\n"
                "💎 **Хотите оформить?**\n"
                "Нажмите кнопку \"💎 Купить подписку\" для выбора тарифа."
            )
        else:
            # Получаем статистику из Marzban
            if subscription.marzban_username:
                marzban_user = await marzban_service.get_user(subscription.marzban_username)
                
                if marzban_user:
                    # Рассчитываем статистику
                    used_gb = marzban_user.used_traffic / (1024**3)
                    limit_gb = marzban_user.data_limit / (1024**3) if marzban_user.data_limit > 0 else 0
                    usage_percent = (used_gb / limit_gb * 100) if limit_gb > 0 else 0
                    
                    expire_date = datetime.fromtimestamp(marzban_user.expire)
                    days_left = (expire_date - datetime.now()).days
                    
                    text = (
                        f"📊 **Ваша статистика**\n\n"
                        f"📅 **Дней осталось:** {days_left}\n"
                        f"📊 **Использовано трафика:** {used_gb:.2f}GB\n"
                        f"📈 **Процент использования:** {usage_percent:.1f}%\n"
                        f"🌐 **Протокол:** {subscription.protocol}\n"
                        f"💰 **Тариф:** {subscription.plan_name}\n"
                    )
                    
                    if marzban_user.status == "limited":
                        text += f"\n⚠️ **Внимание:** Трафик ограничен"
                    elif marzban_user.status == "expired":
                        text += f"\n🕐 **Внимание:** Подписка истекла"
                else:
                    text = (
                        "📊 **Статистика**\n\n"
                        "⚠️ Не удалось загрузить статистику.\n"
                        "Попробуйте позже."
                    )
            else:
                text = (
                    "📊 **Статистика**\n\n"
                    "⚠️ Конфигурация еще не готова.\n"
                    "Попробуйте позже."
                )
        
        keyboard = await get_main_keyboard(message.from_user.id)
        
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в статистике: {format_error_traceback(e)}")
        await message.answer(
            "❌ Произошла ошибка при загрузке статистики.",
            parse_mode=ParseMode.HTML
        )


@user_router.message(F.text == "💬 Поддержка")
async def cmd_support(message: Message):
    """
    Обработчик кнопки "Поддержка"
    """
    try:
        text = (
            "💬 **Поддержка**\n\n"
            "🆘 **Нужна помощь?**\n\n"
            "📝 **Напишите нам:**\n"
            "• Опишите вашу проблему\n"
            "• Укажите ваш Telegram ID: `" + str(message.from_user.id) + "`\n"
            "• Приложите скриншоты если нужно\n\n"
            "⏰ **Время ответа:** обычно 5-15 минут\n\n"
            "💡 **Частые вопросы:**\n"
            "• Как подключить VPN?\n"
            "• Не работает конфигурация\n"
            "• Проблемы с оплатой\n\n"
            "📧 *Мы всегда готовы помочь!*"
        )
        
        keyboard = await get_main_keyboard(message.from_user.id)
        
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в поддержке: {format_error_traceback(e)}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


@user_router.message(F.text == "⚙️ Настройки")
async def cmd_settings(message: Message):
    """
    Обработчик кнопки "Настройки"
    """
    try:
        text = (
            "⚙️ **Настройки**\n\n"
            "👤 **Ваш профиль:**\n"
            f"🆔 ID: `{message.from_user.id}`\n"
            f"👤 Имя: {message.from_user.first_name or 'Не указано'}\n"
            f"🔗 Username: @{message.from_user.username or 'Не указано'}\n\n"
            "💎 **Платежные настройки:**\n"
            "• Способ оплаты: Telegram Stars\n"
            "• Валюта: XTR (звёзды)\n\n"
            "🔔 **Уведомления:**\n"
            "• О статусе подписки: Включены\n"
            "• Об оплате: Включены\n"
            "• Об истечении: Включены\n\n"
            "💡 *Для изменения настроек свяжитесь с поддержкой*"
        )
        
        keyboard = await get_main_keyboard(message.from_user.id)
        
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в настройках: {format_error_traceback(e)}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


# Callback хендлеры
@user_router.callback_query(F.data == "my_subscription")
async def callback_my_subscription(callback: CallbackQuery):
    """
    Callback для "Моя подписка"
    """
    try:
        await cmd_my_subscription(callback.message)
        await callback.answer()
    except Exception as e:
        logger.error(f"❌ Ошибка в callback my_subscription: {format_error_traceback(e)}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@user_router.callback_query(F.data == "payment_history")
async def callback_payment_history(callback: CallbackQuery):
    """
    Callback для "История платежей"
    """
    try:
        from src.handlers.payment_stars import cmd_payment_history
        await cmd_payment_history(callback.message)
        await callback.answer()
    except Exception as e:
        logger.error(f"❌ Ошибка в callback payment_history: {format_error_traceback(e)}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@user_router.callback_query(F.data == "support")
async def callback_support(callback: CallbackQuery):
    """
    Callback для "Поддержка"
    """
    try:
        await cmd_support(callback.message)
        await callback.answer()
    except Exception as e:
        logger.error(f"❌ Ошибка в callback support: {format_error_traceback(e)}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@user_router.callback_query(F.data == "show_main_menu")
async def callback_show_main_menu(callback: CallbackQuery):
    """
    Callback для показа главного меню с reply клавиатурой
    """
    try:
        keyboard = await get_main_keyboard(callback.from_user.id)
        
        await callback.message.answer(
            "🏠 **Главное меню**\n\n"
            "Выберите действие:",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"❌ Ошибка показа главного меню: {format_error_traceback(e)}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@user_router.callback_query(F.data == "back_to_main")
async def callback_back_to_main(callback: CallbackQuery):
    """
    Callback для возврата в главное меню
    """
    try:
        keyboard = await get_back_to_main_inline_keyboard()
        
        await callback.message.edit_text(
            "🏠 **Главное меню**\n\n"
            "Выберите действие:",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"❌ Ошибка возврата в главное меню: {format_error_traceback(e)}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
