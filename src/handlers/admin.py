import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from aiogram import Router, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from sqlalchemy import select, func, and_

from src.core.config import settings
from src.core.database import user_repo, subscription_repo, payment_repo
from src.enums import UserStatus, SubscriptionStatus, PaymentStatus
from src.models import User, Subscription, Payment
from utils.format_error import format_error_traceback

# Create router
admin_router = Router()
logger = logging.getLogger(__name__)
# States
class AdminStates(StatesGroup):
    managing_user = State()
    broadcast_message = State()
    extend_subscription = State()
    user_search = State()
    create_user = State()
    delete_user = State()

class AdminPanel:
    def __init__(self):
        self.admin_id = settings.admin_id
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id == self.admin_id
    
    async def show_main_menu(self, message: Message):
        """Show admin main menu"""
        if not self.is_admin(message.from_user.id):
            return
        
        stats = await self.get_statistics()
        
        text = (
            f"🔧 **Админ панель**\n\n"
            f"📊 **Статистика:**\n"
            f"• Всего пользователей: {stats['total_users']}\n"
            f"• Активных пользователей: {stats['active_users']}\n"
            f"• Активных подписок: {stats['active_subscriptions']}\n"
            f"• Общий доход: ${stats['total_revenue']:.2f}\n"
            f"• Ожидающих платежей: {stats['pending_payments']}\n\n"
            f"Выберите действие:"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users")],
            [InlineKeyboardButton(text="� Поиск пользователя", callback_data="admin_search_user")],
            [InlineKeyboardButton(text="➕ Создать пользователя", callback_data="admin_create_user")],
            [InlineKeyboardButton(text="🗑️ Удалить пользователя", callback_data="admin_delete_user")],
            [InlineKeyboardButton(text="⏰ Продлить подписку", callback_data="admin_extend_subscription")],
            [InlineKeyboardButton(text="� Просмотр платежей", callback_data="admin_payments")],
            [InlineKeyboardButton(text="📊 Детальная статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📢 Рассылка сообщений", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="⚙️ Системные настройки", callback_data="admin_settings")],
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    
    async def delete_user_confirm(self, callback: CallbackQuery, user_id: int):
        """Подтверждение удаления пользователя"""
        try:
            # Удаляем подписки
            await subscription_repo.db.delete_all(Subscription, filters={"user_id": user_id})
            
            # Удаляем платежи
            await payment_repo.db.delete_all(Payment, filters={"user_id": user_id})
            
            # Удаляем пользователя
            await user_repo.db.delete(User, user_id)
            
            await callback.message.edit_text(
                f"✅ **Пользователь удален:**\n\n"
                f"🆔 ID пользователя: {user_id}\n"
                f"🗑️ Все данные удалены",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")]
                ])
            )
            await callback.answer("✅ Пользователь удален")
            
        except Exception as e:
            logger.error(f"[ADMIN-001] Ошибка удаления пользователя: {format_error_traceback(e)}")
            await callback.message.edit_text(f"❌ [ADMIN-001] Ошибка удаления: {e}")
    
    async def extend_user_subscription(self, callback: CallbackQuery, user_id: int):
        """Продление подписки пользователя"""
        try:
            user = await user_repo.get_user(user_id)
            if not user:
                await callback.answer("❌ Пользователь не найден")
                return
            
            # Получаем активную подписку
            subscriptions = await subscription_repo.get_user_subscriptions(user_id)
            active_subscription = next((s for s in subscriptions if s.status == "active"), None)
            
            if not active_subscription:
                await callback.answer("❌ У пользователя нет активной подписки")
                return
            
            # Показываем форму для ввода дней
            await callback.message.edit_text(
                f"⏰ **Продление подписки**\n\n"
                f"👤 Пользователь: @{user.username} (ID: {user.id})\n"
                f"📋 Текущая подписка: {active_subscription.plan_name}\n"
                f"📅 Текущее окончание: {active_subscription.expires_at.strftime('%Y-%m-%d %H:%M')}\n\n"
                f"Введите количество дней для добавления:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")]
                ])
            )
            # Устанавливаем состояние с ID пользователя
            await AdminStates.extend_subscription.set()
            
        except Exception as e:
            logger.error(f"[ADMIN-002] Ошибка продления подписки: {format_error_traceback(e)}")
            await callback.message.edit_text(f"❌ [ADMIN-002] Ошибка: {e}")
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get system statistics"""
        # User statistics
        total_users = await user_repo.count_users()
        active_users = await user_repo.count_users(active_only=True)
        
        # Subscription statistics
        active_subscriptions = await subscription_repo.db.count(
            Subscription, 
            filters={"status": SubscriptionStatus.ACTIVE}
        )
        
        # Payment statistics
        total_revenue = 0.0
        pending_payments = await payment_repo.get_pending_payments()
        
        # Calculate total revenue from completed payments
        all_payments = await payment_repo.db.get_all(
            Payment, 
            filters={"status": PaymentStatus.COMPLETED}
        )
        total_revenue = sum(p.amount for p in all_payments)
        
        # Expiring subscriptions
        expiring_soon = len(await subscription_repo.get_expiring_subscriptions(days_ahead=3))
        
        # Recent registrations (last 7 days)
        from datetime import datetime, timedelta
        week_ago = datetime.now() - timedelta(days=7)
        new_users = await user_repo.db.count(
            User,
            filters={"created_at": week_ago}
        )
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'active_subscriptions': active_subscriptions,
            'total_revenue': total_revenue,
            'pending_payments': len(pending_payments),
            'new_users_week': new_users,
            'expiring_soon': expiring_soon
        }
    
    async def show_users(self, callback: CallbackQuery, page: int = 1):
        """Show users list"""
        if not self.is_admin(callback.from_user.id):
            return
        
        per_page = 10
        offset = (page - 1) * per_page
        
        # Get users with pagination
        users = await user_repo.db.get_all(
            User,
            limit=per_page,
            offset=offset,
            order_by="created_at"
        )
        
        # Get total count
        total_count = await user_repo.db.count(User)
        total_pages = (total_count + per_page - 1) // per_page
        
        if not users:
            await callback.message.edit_text("Пользователи не найдены.")
            return
        
        # Create user list
        text = f"👥 **Пользователи (Страница {page}/{total_pages})**\n\n"
        
        keyboard_buttons = []
        
        for user in users:
            # Get user's subscription status
            active_sub = await subscription_repo.get_active_subscription(user.id)
            
            status_emoji = "🟢" if user.status == UserStatus.ACTIVE else "🔴"
            sub_status = "✅" if active_sub else "❌"
            
            text += (
                f"{status_emoji} ID: {user.telegram_id}\n"
                f"   Статус: {user.status}\n"
                f"   Подписка: {sub_status}\n"
                f"   Зарегистрирован: {user.created_at.strftime('%Y-%m-%d')}\n\n"
            )
            
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"👤 Пользователь {user.telegram_id}", 
                    callback_data=f"admin_user_{user.telegram_id}"
                )
            ])
        
        # Add pagination
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Предыдущая", callback_data=f"admin_users_{page-1}"))
        
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Следующая ➡️", callback_data=f"admin_users_{page+1}"))
        
        if nav_buttons:
            keyboard_buttons.append(nav_buttons)
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 В админ панель", callback_data="admin_main")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    
    async def show_users_message(self, message: Message, page: int = 1):
        """Show users list (for message handlers)"""
        if not self.is_admin(message.from_user.id):
            return
        
        per_page = 10
        offset = (page - 1) * per_page
        
        # Get users with pagination
        users = await user_repo.db.get_all(
            User,
            limit=per_page,
            offset=offset,
            order_by="created_at"
        )
        
        # Get total count
        total_count = await user_repo.db.count(User)
        total_pages = (total_count + per_page - 1) // per_page
        
        if not users:
            await message.answer("Пользователи не найдены.")
            return
        
        # Create user list
        text = f"👥 **Пользователи (Страница {page}/{total_pages})**\n\n"
        
        keyboard_buttons = []
        
        for user in users:
            # Get user's subscription status
            active_sub = await subscription_repo.get_active_subscription(user.id)
            
            status_emoji = "🟢" if user.status == UserStatus.ACTIVE else "🔴"
            sub_status = "✅" if active_sub else "❌"
            
            text += (
                f"{status_emoji} ID: {user.telegram_id}\n"
                f"   Статус: {user.status}\n"
                f"   Подписка: {sub_status}\n"
                f"   Зарегистрирован: {user.created_at.strftime('%Y-%m-%d')}\n\n"
            )
            
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"👤 Пользователь {user.telegram_id}", 
                    callback_data=f"admin_user_{user.telegram_id}"
                )
            ])
        
        # Add pagination
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Предыдущая", callback_data=f"admin_users_{page-1}"))
        
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Следующая ➡️", callback_data=f"admin_users_{page+1}"))
        
        if nav_buttons:
            keyboard_buttons.append(nav_buttons)
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 В админ панель", callback_data="admin_main")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

# Global admin panel instance
admin_panel = AdminPanel()

# Admin keyboard
def get_admin_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Пользователи")],
            [KeyboardButton(text="💳 Платежи")],
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="📢 Рассылка")],
            [KeyboardButton(text="🔙 Главное меню")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

# Admin message handlers
@admin_router.message(F.text == "👥 Пользователи")
async def admin_users(message: Message):
    """Handle admin users command"""
    if admin_panel.is_admin(message.from_user.id):
        await admin_panel.show_users_message(message, 1)

@admin_router.message(F.text == "💳 Платежи")
async def admin_payments(message: Message):
    """Handle admin payments command"""
    if admin_panel.is_admin(message.from_user.id):
        await message.answer("💳 Управление платежами скоро...")

@admin_router.message(F.text == "📊 Статистика")
async def admin_statistics(message: Message):
    """Handle admin statistics command"""
    if admin_panel.is_admin(message.from_user.id):
        await admin_panel.show_main_menu(message)

@admin_router.message(F.text == "📢 Рассылка")
async def admin_broadcast(message: Message):
    """Handle admin broadcast command"""
    if admin_panel.is_admin(message.from_user.id):
        await message.answer("📢 Функция рассылки скоро...")

@admin_router.message(F.text == "⚙️ Настройки")
async def admin_settings(message: Message):
    """Handle admin settings command"""
    if admin_panel.is_admin(message.from_user.id):
        await message.answer("⚙️ Настройки системы скоро...")

@admin_router.message(F.text == "🔙 Главное меню")
async def admin_main_menu(message: Message):
    """Handle admin main menu command"""
    if admin_panel.is_admin(message.from_user.id):
        await admin_panel.show_main_menu(message)

# Admin callback handlers
@admin_router.callback_query(F.data.startswith("admin_"))
async def admin_callback_handler(callback: CallbackQuery):
    """Handle admin callback queries"""
    action = callback.data.replace("admin_", "")
    
    if action == "main":
        await admin_panel.show_main_menu(callback.message)
    elif action.startswith("users_"):
        page = int(action.split("_")[1]) if "_" in action else 1
        await admin_panel.show_users(callback, page)
    elif action.startswith("user_"):
        user_id = int(action.split("_")[1])
        await callback.message.edit_text(f"Детали пользователя {user_id} скоро...")
    elif action == "payments":
        await callback.message.edit_text("💳 Управление платежами скоро...")
    elif action == "stats":
        await callback.message.edit_text("📊 Детальная статистика скоро...")
    elif action == "broadcast":
        await callback.message.edit_text("📢 Рассылка сообщений скоро...")
    elif action == "settings":
        await callback.message.edit_text("⚙️ Настройки системы скоро...")
    elif action == "search_user":
        await callback.message.edit_text(
            "🔍 **Поиск пользователя**\n\n"
            "Введите ID пользователя или username для поиска:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")]
            ])
        )
        await AdminStates.user_search.set()
    elif action == "create_user":
        await callback.message.edit_text(
            "➕ **Создание пользователя**\n\n"
            "Введите данные пользователя в формате:\n"
            "username:telegram_id:plan_name\n\n"
            "Пример: testuser:123456789:basic",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")]
            ])
        )
        await AdminStates.create_user.set()
    elif action == "delete_user":
        await callback.message.edit_text(
            "🗑️ **Удаление пользователя**\n\n"
            "Введите ID пользователя для удаления:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")]
            ])
        )
        await AdminStates.delete_user.set()
    elif action == "extend_subscription":
        await callback.message.edit_text(
            "⏰ **Продление подписки**\n\n"
            "Введите данные в формате:\n"
            "user_id:days\n\n"
            "Пример: 123456789:30",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")]
            ])
        )
        await AdminStates.extend_subscription.set()
    elif action.startswith("delete_confirm_"):
        user_id = int(action.split("_")[2])
        await admin_panel.delete_user_confirm(callback, user_id)
    elif action.startswith("extend_user_"):
        user_id = int(action.split("_")[2])
        await admin_panel.extend_user_subscription(callback, user_id)

# Обработчики сообщений для состояний
@admin_router.message(AdminStates.user_search)
async def handle_user_search(message: Message):
    """Обработка поиска пользователя"""
    if not admin_panel.is_admin(message.from_user.id):
        return
    
    search_query = message.text.strip()
    
    try:
        # Поиск по ID
        if search_query.isdigit():
            user = await user_repo.get_user(int(search_query))
        else:
            # Поиск по username
            user = await user_repo.get_user_by_username(search_query)
        
        if user:
            subscriptions = await subscription_repo.get_user_subscriptions(user.id)
            active_sub = [s for s in subscriptions if s.status == "active"]
            
            text = (
                f"👤 **Найден пользователь:**\n\n"
                f"🆔 ID: {user.id}\n"
                f"👤 Username: @{user.username}\n"
                f"📱 Telegram ID: {user.telegram_id}\n"
                f"📅 Создан: {user.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"📊 Статус: {user.status}\n\n"
                f"📋 Подписки: {len(subscriptions)} (активных: {len(active_sub)})"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🗑️ Удалить пользователя", callback_data=f"admin_delete_confirm_{user.id}")],
                [InlineKeyboardButton(text="⏰ Продлить подписку", callback_data=f"admin_extend_user_{user.id}")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")]
            ])
        else:
            text = f"❌ Пользователь не найден: {search_query}"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")]
            ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
        await AdminStates.user_search.clear()
        
    except Exception as e:
        logger.error(f"[ADMIN-003] Ошибка поиска: {format_error_traceback(e)}")
        await message.answer(f"❌ [ADMIN-003] Ошибка поиска: {e}")
        await AdminStates.user_search.clear()

@admin_router.message(AdminStates.create_user)
async def handle_create_user(message: Message):
    """Обработка создания пользователя"""
    if not admin_panel.is_admin(message.from_user.id):
        return
    
    try:
        parts = message.text.strip().split(':')
        if len(parts) != 3:
            await message.answer("❌ Неверный формат. Используйте: username:telegram_id:plan_name")
            return
        
        username, telegram_id, plan_name = parts
        
        # Создаем пользователя
        user = await user_repo.create_user(
            username=username.strip(),
            telegram_id=int(telegram_id.strip()),
            status="active"
        )
        
        # Создаем подписку
        subscription = await subscription_repo.create_subscription(
            user_id=user.id,
            plan_name=plan_name.strip(),
            status="active"
        )
        
        await message.answer(
            f"✅ **Пользователь создан:**\n\n"
            f"🆔 ID: {user.id}\n"
            f"👤 Username: {username}\n"
            f"📱 Telegram ID: {telegram_id}\n"
            f"📋 План: {plan_name}\n"
            f"📋 Подписка ID: {subscription.id}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")]
            ])
        )
        await AdminStates.create_user.clear()
        
    except Exception as e:
        logger.error(f"[ADMIN-004] Ошибка создания пользователя: {format_error_traceback(e)}")
        await message.answer(f"❌ [ADMIN-004] Ошибка создания пользователя: {e}")
        await AdminStates.create_user.clear()

@admin_router.message(AdminStates.delete_user)
async def handle_delete_user(message: Message):
    """Обработка удаления пользователя"""
    if not admin_panel.is_admin(message.from_user.id):
        return
    
    user_id = message.text.strip()
    
    if not user_id.isdigit():
        await message.answer("❌ Введите корректный ID пользователя")
        return
    
    try:
        user_id = int(user_id)
        user = await user_repo.get_user(user_id)
        
        if not user:
            await message.answer(f"❌ Пользователь с ID {user_id} не найден")
            return
        
        # Подтверждение удаления
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"admin_delete_confirm_{user_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_main")]
        ])
        
        await message.answer(
            f"🗑️ **Подтверждение удаления:**\n\n"
            f"👤 Пользователь: @{user.username} (ID: {user.id})\n"
            f"📱 Telegram ID: {user.telegram_id}\n\n"
            f"⚠️ **Все данные пользователя будут удалены!**",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        await AdminStates.delete_user.clear()
        
    except Exception as e:
        logger.error(f"[ADMIN-005] Ошибка удаления пользователя: {format_error_traceback(e)}")
        await message.answer(f"❌ [ADMIN-005] Ошибка: {e}")
        await AdminStates.delete_user.clear()

@admin_router.message(AdminStates.extend_subscription)
async def handle_extend_subscription(message: Message):
    """Обработка продления подписки"""
    if not admin_panel.is_admin(message.from_user.id):
        return
    
    try:
        parts = message.text.strip().split(':')
        if len(parts) != 2:
            await message.answer("❌ Неверный формат. Используйте: user_id:days")
            return
        
        user_id, days = parts
        user_id = int(user_id.strip())
        days = int(days.strip())
        
        user = await user_repo.get_user(user_id)
        if not user:
            await message.answer(f"❌ Пользователь с ID {user_id} не найден")
            return
        
        # Получаем активную подписку
        subscriptions = await subscription_repo.get_user_subscriptions(user_id)
        active_subscription = next((s for s in subscriptions if s.status == "active"), None)
        
        if active_subscription:
            # Продлеваем существующую подписку
            from datetime import datetime, timedelta
            new_expiry = active_subscription.expires_at + timedelta(days=days)
            
            await subscription_repo.db.update(
                Subscription, 
                active_subscription.id, 
                expires_at=new_expiry
            )
            
            await message.answer(
                f"✅ **Подписка продлена:**\n\n"
                f"👤 Пользователь: @{user.username} (ID: {user.id})\n"
                f"📅 Новая дата окончания: {new_expiry.strftime('%Y-%m-%d %H:%M')}\n"
                f"⏰ Добавлено дней: {days}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")]
                ])
            )
        else:
            await message.answer(f"❌ У пользователя нет активной подписки")
        
        await AdminStates.extend_subscription.clear()
        
    except Exception as e:
        logger.error(f"[ADMIN-006] Ошибка продления подписки: {format_error_traceback(e)}")
        await message.answer(f"❌ [ADMIN-006] Ошибка продления: {e}")
        await AdminStates.extend_subscription.clear()
