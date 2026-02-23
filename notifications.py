import asyncio
from datetime import datetime, timedelta
from typing import List
from sqlalchemy import select, and_
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings
from database import get_db_context
from models import User, Subscription, NotificationLog, SubscriptionStatus
from bot import bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class NotificationService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.setup_scheduler()
    
    def setup_scheduler(self):
        """Setup scheduled tasks"""
        # Check for expiring subscriptions every day at 9:00 AM
        self.scheduler.add_job(
            self.check_expiring_subscriptions,
            CronTrigger(hour=9, minute=0),
            id="check_expiring",
            name="Check expiring subscriptions",
            replace_existing=True
        )
        
        # Check for expired subscriptions every hour
        self.scheduler.add_job(
            self.check_expired_subscriptions,
            CronTrigger(minute=0),
            id="check_expired",
            name="Check expired subscriptions",
            replace_existing=True
        )
    
    async def start(self):
        """Start the notification scheduler"""
        self.scheduler.start()
        print("Notification scheduler started")
    
    async def stop(self):
        """Stop the notification scheduler"""
        self.scheduler.shutdown()
        print("Notification scheduler stopped")
    
    async def check_expiring_subscriptions(self):
        """Check for subscriptions that will expire soon"""
        async with get_db_context() as db:
            now = datetime.now()
            
            for days in settings.expiry_notification_days:
                expiry_date = now + timedelta(days=days)
                
                # Find subscriptions expiring on this date
                query = select(Subscription).where(
                    and_(
                        Subscription.status == SubscriptionStatus.ACTIVE,
                        Subscription.expires_at >= expiry_date.replace(hour=0, minute=0, second=0),
                        Subscription.expires_at <= expiry_date.replace(hour=23, minute=59, second=59)
                    )
                )
                
                result = await db.execute(query)
                subscriptions = result.scalars().all()
                
                for subscription in subscriptions:
                    await self.send_expiry_notification(subscription, days)
    
    async def check_expired_subscriptions(self):
        """Check for expired subscriptions and deactivate them"""
        async with get_db_context() as db:
            now = datetime.now()
            
            # Find expired subscriptions
            query = select(Subscription).where(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.expires_at <= now
                )
            )
            
            result = await db.execute(query)
            subscriptions = result.scalars().all()
            
            for subscription in subscriptions:
                await self.deactivate_subscription(subscription)
    
    async def send_expiry_notification(self, subscription: Subscription, days_remaining: int):
        """Send expiry notification to user"""
        try:
            user = subscription.user
            
            # Check if notification was already sent for this period
            existing_log = await db.execute(
                select(NotificationLog).where(
                    and_(
                        NotificationLog.user_id == user.id,
                        NotificationLog.notification_type == f"expiry_warning_{days_remaining}d",
                        NotificationLog.created_at >= datetime.now().replace(hour=0, minute=0, second=0)
                    )
                )
            )
            
            if existing_log.scalar():
                return  # Already sent today
            
            # Create notification message
            message = (
                f"⚠️ **Subscription Expiry Warning**\n\n"
                f"Dear {user.first_name or 'User'},\n\n"
                f"Your VPN subscription will expire in **{days_remaining} days**!\n\n"
                f"📋 **Subscription Details:**\n"
                f"• Plan: {subscription.plan_name.replace('_', ' ').title()}\n"
                f"• Protocol: {subscription.protocol.upper()}\n"
                f"• Expires: {subscription.expires_at.strftime('%Y-%m-%d %H:%M')}\n\n"
                f"🔄 **To renew your subscription:**\n"
                f"1. Click '💰 Buy Subscription'\n"
                f"2. Choose your preferred plan\n"
                f"3. Complete the payment\n\n"
                f"❌ **If you don't renew:**\n"
                f"Your VPN access will be automatically disabled after expiry.\n\n"
                f"Need help? Contact @{settings.support_username}"
            )
            
            # Send message
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Renew Now", callback_data=f"renew_{subscription.id}")],
                [InlineKeyboardButton(text="📱 View Subscription", callback_data="view_subscription")],
                [InlineKeyboardButton(text="🆘 Support", callback_data="contact_support")]
            ])
            
            await bot.send_message(
                user.telegram_id,
                message,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            # Log notification
            notification_log = NotificationLog(
                user_id=user.id,
                notification_type=f"expiry_warning_{days_remaining}d",
                message=message,
                success=True
            )
            db.add(notification_log)
            await db.commit()
            
            print(f"Sent expiry notification to user {user.telegram_id} ({days_remaining} days remaining)")
            
        except Exception as e:
            print(f"Failed to send expiry notification: {e}")
            
            # Log failed notification
            async with get_db_context() as db:
                notification_log = NotificationLog(
                    user_id=subscription.user_id,
                    notification_type=f"expiry_warning_{days_remaining}d",
                    message="Failed to send expiry notification",
                    success=False,
                    error_message=str(e)
                )
                db.add(notification_log)
                await db.commit()
    
    async def deactivate_subscription(self, subscription: Subscription):
        """Deactivate expired subscription"""
        try:
            user = subscription.user
            
            # Update subscription status
            subscription.status = SubscriptionStatus.EXPIRED
            
            # Deactivate user in Marzban
            if user.marzban_username:
                from marzban_api import marzban_api
                await marzban_api.update_user(
                    user.marzban_username,
                    {"status": "disabled"}
                )
            
            # Send notification to user
            message = (
                f"❌ **Subscription Expired**\n\n"
                f"Dear {user.first_name or 'User'},\n\n"
                f"Your VPN subscription has expired.\n\n"
                f"📋 **Expired Subscription:**\n"
                f"• Plan: {subscription.plan_name.replace('_', ' ').title()}\n"
                f"• Protocol: {subscription.protocol.upper()}\n"
                f"• Expired: {subscription.expires_at.strftime('%Y-%m-%d %H:%M')}\n\n"
                f"🔄 **To reactivate your service:**\n"
                f"1. Click '💰 Buy Subscription'\n"
                f"2. Choose your preferred plan\n"
                f"3. Complete the payment\n\n"
                f"Need help? Contact @{settings.support_username}"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Renew Now", callback_data=f"renew_{subscription.id}")],
                [InlineKeyboardButton(text="🆘 Support", callback_data="contact_support")]
            ])
            
            await bot.send_message(
                user.telegram_id,
                message,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            # Log notification
            notification_log = NotificationLog(
                user_id=user.id,
                notification_type="subscription_expired",
                message=message,
                success=True
            )
            
            async with get_db_context() as db:
                db.add(notification_log)
                db.add(subscription)
                await db.commit()
            
            print(f"Deactivated subscription {subscription.id} for user {user.telegram_id}")
            
        except Exception as e:
            print(f"Failed to deactivate subscription: {e}")
    
    async def send_payment_confirmation(self, user_id: int, subscription: Subscription):
        """Send payment confirmation and activation message"""
        try:
            message = (
                f"✅ **Payment Confirmed!**\n\n"
                f"Congratulations! Your VPN subscription is now **ACTIVE**.\n\n"
                f"📋 **Subscription Details:**\n"
                f"• Plan: {subscription.plan_name.replace('_', ' ').title()}\n"
                f"• Protocol: {subscription.protocol.upper()}\n"
                f"• Started: {subscription.started_at.strftime('%Y-%m-%d %H:%M') if subscription.started_at else 'Now'}\n"
                f"• Expires: {subscription.expires_at.strftime('%Y-%m-%d %H:%M') if subscription.expires_at else 'N/A'}\n\n"
            )
            
            if subscription.subscription_url:
                message += f"🔗 **Your Subscription URL:**\n`{subscription.subscription_url}`\n\n"
                message += "📱 **How to use:**\n"
                message += "1. Copy the subscription URL above\n"
                message += "2. Add it to your VPN client\n"
                message += "3. Connect and enjoy!\n\n"
            
            message += f"Need help? Contact @{settings.support_username}"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📱 View Subscription", callback_data="view_subscription")],
                [InlineKeyboardButton(text="⚙️ Change Protocol", callback_data="change_protocol")],
                [InlineKeyboardButton(text="🆘 Support", callback_data="contact_support")]
            ])
            
            await bot.send_message(
                user_id,
                message,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            # Log notification
            notification_log = NotificationLog(
                user_id=user_id,
                notification_type="payment_confirmed",
                message=message,
                success=True
            )
            
            async with get_db_context() as db:
                db.add(notification_log)
                await db.commit()
            
        except Exception as e:
            print(f"Failed to send payment confirmation: {e}")
    
    async def send_welcome_message(self, user_id: int, user_name: str):
        """Send welcome message to new users"""
        try:
            message = (
                f"🎉 **Welcome to VPN Service!**\n\n"
                f"Hello {user_name}!\n\n"
                f"🚀 **Getting Started:**\n"
                f"1. Choose a subscription plan\n"
                f"2. Complete the payment\n"
                f"3. Get your VPN configuration\n"
                f"4. Connect and enjoy secure browsing!\n\n"
                f"💰 **Available Plans:**\n"
                f"• 1 Month - $10\n"
                f"• 3 Months - $25 (Save $5)\n"
                f"• 6 Months - $45 (Save $15)\n"
                f"• 1 Year - $80 (Save $40)\n\n"
                f"🔒 **Features:**\n"
                f"• Multiple protocols (VLESS, VMESS, Trojan, Shadowsocks)\n"
                f"• High-speed servers\n"
                f"• No logs policy\n"
                f"• 24/7 support\n\n"
                f"Ready to start? Click '💰 Buy Subscription' below!\n\n"
                f"Need help? Contact @{settings.support_username}"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Buy Subscription", callback_data="buy_subscription")],
                [InlineKeyboardButton(text="📖 How to Use", callback_data="how_to_use")],
                [InlineKeyboardButton(text="🆘 Support", callback_data="contact_support")]
            ])
            
            await bot.send_message(
                user_id,
                message,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            print(f"Failed to send welcome message: {e}")

# Global instance
notification_service = NotificationService()
