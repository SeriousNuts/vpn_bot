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

# Create router
admin_router = Router()

# States
class AdminStates(StatesGroup):
    managing_user = State()
    broadcast_message = State()
    extend_subscription = State()
    user_search = State()

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
            [InlineKeyboardButton(text="💳 Просмотр платежей", callback_data="admin_payments")],
            [InlineKeyboardButton(text="📊 Детальная статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📢 Рассылка сообщений", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="⚙️ Системные настройки", callback_data="admin_settings")],
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    
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
