from typing import List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, or_
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import settings
from database import get_db_context
from models import User, Subscription, Payment, UserStatus, SubscriptionStatus, PaymentStatus, AdminAction
from marzban_api import marzban_api
from cryptobot_payment import payment_processor

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
    
    async def show_user_details(self, callback: CallbackQuery, user_id: int):
        """Show detailed user information"""
        if not self.is_admin(callback.from_user.id):
            return
        
        async with get_db_context() as db:
            user = await db.get(User, user_id)
            if not user:
                await callback.message.edit_text("User not found.")
                return
            
            # Get user's subscriptions
            query = select(Subscription).where(Subscription.user_id == user_id).order_by(Subscription.created_at.desc())
            result = await db.execute(query)
            subscriptions = result.scalars().all()
            
            # Get user's payments
            query = select(Payment).where(Payment.user_id == user_id).order_by(Payment.created_at.desc())
            result = await db.execute(query)
            payments = result.scalars().all()
            
            # Build user info
            status_emoji = {"active": "🟢", "inactive": "🟡", "banned": "🔴"}.get(user.status, "⚪")
            
            text = (
                f"👤 **User Details**\n\n"
                f"{status_emoji} **Status:** {user.status.title()}\n"
                f"🆔 **Telegram ID:** {user.telegram_id}\n"
                f"👤 **Name:** {user.first_name or 'N/A'} {user.last_name or ''}\n"
                f"🔗 **Username:** @{user.username or 'N/A'}\n"
                f"📱 **Phone:** {user.phone or 'N/A'}\n"
                f"📧 **Email:** {user.email or 'N/A'}\n"
                f"📅 **Joined:** {user.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            )
            
            # Subscription info
            if subscriptions:
                text += "📱 **Subscriptions:**\n"
                for sub in subscriptions:
                    status_emoji = {"active": "✅", "expired": "❌", "pending": "⏳"}.get(sub.status, "❓")
                    remaining = (sub.expires_at - datetime.now()).days if sub.expires_at and sub.status == SubscriptionStatus.ACTIVE else 0
                    
                    text += (
                        f"{status_emoji} {sub.plan_name.replace('_', ' ').title()}\n"
                        f"   Protocol: {sub.protocol.upper()}\n"
                        f"   Price: ${sub.price}\n"
                        f"   Status: {sub.status.title()}\n"
                    )
                    
                    if sub.status == SubscriptionStatus.ACTIVE and sub.expires_at:
                        text += f"   Remaining: {remaining} days\n"
                    
                    text += "\n"
            else:
                text += "📱 **Subscriptions:** None\n\n"
            
            # Payment info
            if payments:
                text += "💳 **Recent Payments:**\n"
                for payment in payments[:5]:  # Show last 5 payments
                    status_emoji = {"completed": "✅", "pending": "⏳", "failed": "❌"}.get(payment.status, "❓")
                    
                    text += (
                        f"{status_emoji} ${payment.amount} - {payment.payment_method}\n"
                        f"   Status: {payment.status.title()}\n"
                        f"   Date: {payment.created_at.strftime('%Y-%m-%d')}\n\n"
                    )
            
            # Action buttons
            keyboard_buttons = []
            
            if user.status == UserStatus.ACTIVE:
                keyboard_buttons.append([InlineKeyboardButton(text="🚫 Ban User", callback_data=f"admin_ban_{user_id}")])
            elif user.status == UserStatus.BANNED:
                keyboard_buttons.append([InlineKeyboardButton(text="✅ Unban User", callback_data=f"admin_unban_{user_id}")])
            
            # Find active subscription
            active_sub = None
            for sub in subscriptions:
                if sub.status == SubscriptionStatus.ACTIVE:
                    active_sub = sub
                    break
            
            if active_sub:
                keyboard_buttons.extend([
                    [InlineKeyboardButton(text="⏰ Extend Subscription", callback_data=f"admin_extend_{active_sub.id}")],
                    [InlineKeyboardButton(text="🔄 Change Protocol", callback_data=f"admin_change_proto_{active_sub.id}")],
                    [InlineKeyboardButton(text="🚫 Deactivate Subscription", callback_data=f"admin_deactivate_{active_sub.id}")]
                ])
            else:
                keyboard_buttons.append([InlineKeyboardButton(text="📱 Create Subscription", callback_data=f"admin_create_sub_{user_id}")])
            
            keyboard_buttons.append([InlineKeyboardButton(text="🔙 Back to Users", callback_data="admin_users_1")])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    
    async def show_payments(self, callback: CallbackQuery, page: int = 1, status: str = None):
        """Show payments list"""
        if not self.is_admin(callback.from_user.id):
            return
        
        per_page = 15
        offset = (page - 1) * per_page
        
        async with get_db_context() as db:
            # Build query
            query = select(Payment).order_by(Payment.created_at.desc())
            
            if status:
                query = query.where(Payment.status == status)
            
            # Get payments with pagination
            query = query.offset(offset).limit(per_page)
            result = await db.execute(query)
            payments = result.scalars().all()
            
            # Get total count
            count_query = select(func.count(Payment.id))
            if status:
                count_query = count_query.where(Payment.status == status)
            
            total_count = await db.scalar(count_query)
            total_pages = (total_count + per_page - 1) // per_page
            
            if not payments:
                await callback.message.edit_text("No payments found.")
                return
            
            # Create payment list
            status_filter = f" ({status.title()})" if status else ""
            text = f"💳 **Payments{status_filter} (Page {page}/{total_pages})**\n\n"
            
            keyboard_buttons = []
            
            for payment in payments:
                user = payment.user
                status_emoji = {"completed": "✅", "pending": "⏳", "failed": "❌", "refunded": "💸"}.get(payment.status, "❓")
                
                text += (
                    f"{status_emoji} **${payment.amount}** - {payment.payment_method}\n"
                    f"👤 User: {user.first_name or user.telegram_id}\n"
                    f"🆔 Payment ID: {payment.id}\n"
                    f"📅 Date: {payment.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                    f"📝 {payment.description or 'No description'}\n\n"
                )
            
            # Filter buttons
            filter_buttons = [
                InlineKeyboardButton(text="All", callback_data="admin_payments_all"),
                InlineKeyboardButton(text="✅ Completed", callback_data="admin_payments_completed"),
                InlineKeyboardButton(text="⏳ Pending", callback_data="admin_payments_pending"),
                InlineKeyboardButton(text="❌ Failed", callback_data="admin_payments_failed")
            ]
            keyboard_buttons.append(filter_buttons)
            
            # Pagination
            nav_buttons = []
            if page > 1:
                nav_buttons.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"admin_payments_{page-1}"))
            
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"admin_payments_{page+1}"))
            
            if nav_buttons:
                keyboard_buttons.append(nav_buttons)
            
            keyboard_buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="admin_main")])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    
    async def ban_user(self, callback: CallbackQuery, user_id: int):
        """Ban a user"""
        if not self.is_admin(callback.from_user.id):
            return
        
        async with get_db_context() as db:
            user = await db.get(User, user_id)
            if not user:
                await callback.message.edit_text("User not found.")
                return
            
            # Update user status
            user.status = UserStatus.BANNED
            
            # Deactivate all subscriptions
            query = select(Subscription).where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.status == SubscriptionStatus.ACTIVE
                )
            )
            result = await db.execute(query)
            active_subscriptions = result.scalars().all()
            
            for subscription in active_subscriptions:
                subscription.status = SubscriptionStatus.CANCELLED
                
                # Deactivate in Marzban
                if user.marzban_username:
                    await marzban_api.update_user(
                        user.marzban_username,
                        {"status": "disabled"}
                    )
            
            # Log admin action
            action = AdminAction(
                admin_id=callback.from_user.id,
                action_type="user_ban",
                target_user_id=user_id,
                details={"previous_status": user.status}
            )
            db.add(action)
            
            await db.commit()
            
            await callback.message.edit_text(
                f"✅ User {user.first_name or user.telegram_id} has been banned.\n"
                f"All active subscriptions have been deactivated."
            )
    
    async def extend_subscription(self, callback: CallbackQuery, subscription_id: int):
        """Show subscription extension options"""
        if not self.is_admin(callback.from_user.id):
            return
        
        async with get_db_context() as db:
            subscription = await db.get(Subscription, subscription_id)
            if not subscription:
                await callback.message.edit_text("Subscription not found.")
                return
        
        # Show extension options
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="+7 Days", callback_data=f"admin_extend_days_{subscription_id}_7")],
            [InlineKeyboardButton(text="+30 Days", callback_data=f"admin_extend_days_{subscription_id}_30")],
            [InlineKeyboardButton(text="+90 Days", callback_data=f"admin_extend_days_{subscription_id}_90")],
            [InlineKeyboardButton(text="+365 Days", callback_data=f"admin_extend_days_{subscription_id}_365")],
            [InlineKeyboardButton(text="🔙 Back", callback_data=f"admin_user_{subscription.user_id}")]
        ])
        
        await callback.message.edit_text(
            f"⏰ **Extend Subscription**\n\n"
            f"User: {subscription.user.first_name or subscription.user.telegram_id}\n"
            f"Plan: {subscription.plan_name.replace('_', ' ').title()}\n"
            f"Current expiry: {subscription.expires_at.strftime('%Y-%m-%d') if subscription.expires_at else 'N/A'}\n\n"
            f"Choose extension period:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    async def extend_subscription_days(self, callback: CallbackQuery, subscription_id: int, days: int):
        """Extend subscription by specified days"""
        if not self.is_admin(callback.from_user.id):
            return
        
        async with get_db_context() as db:
            subscription = await db.get(Subscription, subscription_id)
            if not subscription:
                await callback.message.edit_text("Subscription not found.")
                return
            
            user = subscription.user
            
            # Extend in Marzban
            if user.marzban_username:
                success = await marzban_api.extend_user_subscription(user.marzban_username, days)
                
                if success:
                    # Update expiry date in database
                    if subscription.expires_at:
                        subscription.expires_at += timedelta(days=days)
                    else:
                        subscription.expires_at = datetime.now() + timedelta(days=days)
                    
                    # Log admin action
                    action = AdminAction(
                        admin_id=callback.from_user.id,
                        action_type="subscription_extend",
                        target_user_id=user.id,
                        details={"subscription_id": subscription_id, "days": days}
                    )
                    db.add(action)
                    
                    await db.commit()
                    
                    await callback.message.edit_text(
                        f"✅ Subscription extended by {days} days!\n\n"
                        f"New expiry date: {subscription.expires_at.strftime('%Y-%m-%d')}"
                    )
                else:
                    await callback.message.edit_text("❌ Failed to extend subscription in Marzban.")
            else:
                await callback.message.edit_text("❌ User not found in Marzban.")

# Global admin panel instance
admin_panel = AdminPanel()
