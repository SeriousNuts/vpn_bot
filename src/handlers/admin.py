from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, or_
from aiogram import Router, F, types
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.context import FSMContext

from src.core.config import settings
from src.core.database import get_db_context
from src.models import User, Subscription, Payment, AdminAction
from src.enums import UserStatus, SubscriptionStatus, PaymentStatus
from src.services.marzban import marzban_api

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
            f"🔧 **Admin Panel**\n\n"
            f"📊 **Statistics:**\n"
            f"• Total Users: {stats['total_users']}\n"
            f"• Active Users: {stats['active_users']}\n"
            f"• Active Subscriptions: {stats['active_subscriptions']}\n"
            f"• Total Revenue: ${stats['total_revenue']:.2f}\n"
            f"• Pending Payments: {stats['pending_payments']}\n\n"
            f"Choose an action:"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Manage Users", callback_data="admin_users")],
            [InlineKeyboardButton(text="💳 View Payments", callback_data="admin_payments")],
            [InlineKeyboardButton(text="📊 Detailed Stats", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📢 Broadcast Message", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="⚙️ System Settings", callback_data="admin_settings")],
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get system statistics"""
        async with get_db_context() as db:
            # User statistics
            total_users = await db.scalar(select(func.count(User.id)))
            active_users = await db.scalar(
                select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)
            )
            
            # Subscription statistics
            active_subscriptions = await db.scalar(
                select(func.count(Subscription.id)).where(
                    Subscription.status == SubscriptionStatus.ACTIVE
                )
            )
            
            # Payment statistics
            total_revenue = await db.scalar(
                select(func.sum(Payment.amount)).where(
                    Payment.status == PaymentStatus.COMPLETED
                )
            ) or 0
            
            pending_payments = await db.scalar(
                select(func.count(Payment.id)).where(
                    Payment.status == PaymentStatus.PENDING
                )
            )
            
            # Recent registrations (last 7 days)
            week_ago = datetime.now() - timedelta(days=7)
            new_users = await db.scalar(
                select(func.count(User.id)).where(User.created_at >= week_ago)
            )
            
            # Expiring soon (next 7 days)
            next_week = datetime.now() + timedelta(days=7)
            expiring_soon = await db.scalar(
                select(func.count(Subscription.id)).where(
                    and_(
                        Subscription.status == SubscriptionStatus.ACTIVE,
                        Subscription.expires_at <= next_week,
                        Subscription.expires_at >= datetime.now()
                    )
                )
            )
            
            return {
                'total_users': total_users or 0,
                'active_users': active_users or 0,
                'active_subscriptions': active_subscriptions or 0,
                'total_revenue': total_revenue,
                'pending_payments': pending_payments or 0,
                'new_users_week': new_users or 0,
                'expiring_soon': expiring_soon or 0
            }
    
    async def show_users(self, callback: CallbackQuery, page: int = 1):
        """Show users list"""
        if not self.is_admin(callback.from_user.id):
            return
        
        per_page = 10
        offset = (page - 1) * per_page
        
        async with get_db_context() as db:
            # Get users with pagination
            query = select(User).order_by(User.created_at.desc()).offset(offset).limit(per_page)
            result = await db.execute(query)
            users = result.scalars().all()
            
            # Get total count
            total_count = await db.scalar(select(func.count(User.id)))
            total_pages = (total_count + per_page - 1) // per_page
            
            if not users:
                await callback.message.edit_text("No users found.")
                return
            
            # Create user list
            text = f"👥 **Users (Page {page}/{total_pages})**\n\n"
            
            keyboard_buttons = []
            
            for user in users:
                # Get user's subscription status
                active_sub = None
                for sub in user.subscriptions:
                    if sub.status == SubscriptionStatus.ACTIVE:
                        active_sub = sub
                        break
                
                status_emoji = "🟢" if user.status == UserStatus.ACTIVE else "🔴"
                sub_status = "✅" if active_sub else "❌"
                
                text += (
                    f"{status_emoji} {user.first_name or 'N/A'} (@{user.username or 'N/A'})\n"
                    f"🆔 ID: {user.telegram_id}\n"
                    f"📱 Sub: {sub_status}\n"
                    f"📅 Joined: {user.created_at.strftime('%Y-%m-%d')}\n\n"
                )
                
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"👤 {user.first_name or user.telegram_id}",
                        callback_data=f"admin_user_{user.id}"
                    )
                ])
            
            # Add pagination
            nav_buttons = []
            if page > 1:
                nav_buttons.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"admin_users_{page-1}"))
            
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"admin_users_{page+1}"))
            
            if nav_buttons:
                keyboard_buttons.append(nav_buttons)
            
            keyboard_buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="admin_main")])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

# Global admin panel instance
admin_panel = AdminPanel()

# Admin keyboard
def get_admin_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Users")],
            [KeyboardButton(text="💳 Payments")],
            [KeyboardButton(text="📊 Statistics")],
            [KeyboardButton(text="📢 Broadcast")],
            [KeyboardButton(text="🔙 Main Menu")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

# Admin message handlers
@admin_router.message(F.text == "👥 Users")
async def admin_users(message: Message):
    """Handle admin users command"""
    if admin_panel.is_admin(message.from_user.id):
        await admin_panel.show_users(CallbackQuery(id="temp", message=message), 1)

@admin_router.message(F.text == "💳 Payments")
async def admin_payments(message: Message):
    """Handle admin payments command"""
    if admin_panel.is_admin(message.from_user.id):
        await message.answer("💳 Payment management coming soon...")

@admin_router.message(F.text == "📊 Statistics")
async def admin_statistics(message: Message):
    """Handle admin statistics command"""
    if admin_panel.is_admin(message.from_user.id):
        await admin_panel.show_main_menu(message)

@admin_router.message(F.text == "📢 Broadcast")
async def admin_broadcast(message: Message):
    """Handle admin broadcast command"""
    if admin_panel.is_admin(message.from_user.id):
        await message.answer("📢 Broadcast feature coming soon...")

@admin_router.message(F.text == "🔙 Main Menu")
async def admin_main_menu(message: Message):
    """Handle admin main menu command"""
    if admin_panel.is_admin(message.from_user.id):
        await admin_panel.show_main_menu(message)

# Admin callback handlers
@admin_router.callback_query(F.data.startswith("admin_"))
async def admin_callback_handler(callback: CallbackQuery):
    """Handle admin panel callbacks"""
    if not admin_panel.is_admin(callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return
    
    action = callback.data.replace("admin_", "")
    
    if action == "main":
        await admin_panel.show_main_menu(callback.message)
    elif action.startswith("users_"):
        page = int(action.split("_")[1]) if "_" in action else 1
        await admin_panel.show_users(callback, page)
    elif action.startswith("user_"):
        user_id = int(action.split("_")[1])
        await callback.message.edit_text(f"User details for {user_id} coming soon...")
    elif action.startswith("ban_"):
        user_id = int(action.split("_")[1])
        await callback.message.edit_text(f"Banning user {user_id}...")
    elif action.startswith("unban_"):
        user_id = int(action.split("_")[1])
        await callback.message.edit_text(f"Unbanning user {user_id}...")
    elif action.startswith("extend_"):
        subscription_id = int(action.split("_")[1])
        await callback.message.edit_text(f"Extending subscription {subscription_id}...")
    else:
        await callback.answer("Action coming soon...")
