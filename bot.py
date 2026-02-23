import asyncio
import logging
from datetime import datetime, timedelta
from typing import Union

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from database import init_db, get_db_context
from models import User, Subscription, Payment, UserStatus, SubscriptionStatus, PaymentStatus, ProtocolType
from marzban_api import marzban_api
from cryptobot_payment import payment_processor
from notifications import notification_service
from admin_panel import admin_panel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=settings.bot_token)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# States
class RegistrationStates(StatesGroup):
    phone = State()
    email = State()

class PurchaseStates(StatesGroup):
    plan = State()
    protocol = State()

class SupportStates(StatesGroup):
    message = State()

# Keyboards
def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 My Subscription")],
            [KeyboardButton(text="💰 Buy Subscription")],
            [KeyboardButton(text="⚙️ Settings")],
            [KeyboardButton(text="🆘 Support")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

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

def get_plans_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 Month - $10", callback_data="plan_1_month")],
        [InlineKeyboardButton(text="3 Months - $25", callback_data="plan_3_months")],
        [InlineKeyboardButton(text="6 Months - $45", callback_data="plan_6_months")],
        [InlineKeyboardButton(text="1 Year - $80", callback_data="plan_1_year")],
    ])
    return keyboard

def get_protocol_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="VLESS", callback_data="protocol_vless")],
        [InlineKeyboardButton(text="VMESS", callback_data="protocol_vmess")],
        [InlineKeyboardButton(text="Trojan", callback_data="protocol_trojan")],
        [InlineKeyboardButton(text="Shadowsocks", callback_data="protocol_shadowsocks")],
    ])
    return keyboard

# Handlers
@dp.message(CommandStart())
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
            
            keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="📱 Share Phone", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await message.answer(welcome_text, reply_markup=keyboard)
            await state.set_state(RegistrationStates.phone)
        else:
            # Existing user
            if message.from_user.id == settings.admin_id:
                keyboard = get_admin_keyboard()
                await message.answer("👋 Welcome Admin!", reply_markup=keyboard)
            else:
                keyboard = get_main_keyboard(message.from_user.id)
                await message.answer("👋 Welcome back!", reply_markup=keyboard)

@dp.message(F.contact, RegistrationStates.phone)
async def process_phone(message: Message, state: FSMContext):
    """Process phone number"""
    phone = message.contact.phone_number
    
    async with get_db_context() as db:
        user = await db.get(User, message.from_user.id)
        if user:
            user.phone = phone
            await db.commit()
    
    await message.answer(
        "✅ Phone number saved!\n\n"
        "Now please provide your email address:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(RegistrationStates.email)

@dp.message(RegistrationStates.email)
async def process_email(message: Message, state: FSMContext):
    """Process email"""
    email = message.text.strip()
    
    # Basic email validation
    if "@" not in email or "." not in email:
        await message.answer("❌ Invalid email format. Please try again:")
        return
    
    async with get_db_context() as db:
        user = await db.get(User, message.from_user.id)
        if user:
            user.email = email
            await db.commit()
    
    await message.answer(
        "✅ Registration completed!\n\n"
        "You can now purchase a subscription and manage your VPN service.",
        reply_markup=get_main_keyboard(message.from_user.id)
    )
    await state.clear()

@dp.message(F.text == "💰 Buy Subscription")
async def buy_subscription(message: Message, state: FSMContext):
    """Handle buy subscription"""
    await message.answer(
        "💰 Choose your subscription plan:",
        reply_markup=get_plans_keyboard()
    )
    await state.set_state(PurchaseStates.plan)

@dp.callback_query(F.data.startswith("plan_"), PurchaseStates.plan)
async def process_plan_selection(callback: CallbackQuery, state: FSMContext):
    """Process plan selection"""
    plan = callback.data.replace("plan_", "")
    price = settings.subscription_prices[plan]
    
    await state.update_data(plan=plan, price=price)
    
    await callback.message.edit_text(
        f"✅ Plan selected: {plan.replace('_', ' ').title()}\n"
        f"💰 Price: ${price}\n\n"
        "Now choose your preferred protocol:",
        reply_markup=get_protocol_keyboard()
    )
    await state.set_state(PurchaseStates.protocol)

@dp.callback_query(F.data.startswith("protocol_"), PurchaseStates.protocol)
async def process_protocol_selection(callback: CallbackQuery, state: FSMContext):
    """Process protocol selection"""
    protocol = callback.data.replace("protocol_", "")
    data = await state.get_data()
    plan = data["plan"]
    price = data["price"]
    
    # Create pending subscription
    async with get_db_context() as db:
        user = await db.get(User, callback.from_user.id)
        
        subscription = Subscription(
            user_id=user.id,
            plan_name=plan,
            price=price,
            duration_days=get_duration_days(plan),
            status=SubscriptionStatus.PENDING,
            protocol=protocol
        )
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)
        
        # Create pending payment
        payment = Payment(
            user_id=user.id,
            subscription_id=subscription.id,
            amount=price,
            payment_method="cryptobot",
            description=f"VPN Subscription - {plan.replace('_', ' ').title()}"
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
    
    # Create CryptoBot payment
    payment_info = await payment_processor.create_payment(
        amount=price,
        description=f"VPN Subscription - {plan.replace('_', ' ').title()}",
        user_id=callback.from_user.id,
        payment_id=payment.id
    )
    
    if payment_info:
        # Update payment with external ID
        async with get_db_context() as db:
            payment = await db.get(Payment, payment.id)
            payment.payment_id = payment_info["invoice_id"]
            await db.commit()
        
        await callback.message.edit_text(
            f"✅ Configuration saved!\n\n"
            f"📋 **Order Summary:**\n"
            f"Plan: {plan.replace('_', ' ').title()}\n"
            f"Protocol: {protocol.upper()}\n"
            f"Price: ${price}\n\n"
            f"💳 **Payment Details:**\n"
            f"Payment ID: #{payment.id}\n"
            f"Amount: ${price} USDT\n\n"
            f"🔗 **Click to Pay:**\n"
            f"[Pay Now]({payment_info['pay_url']})\n\n"
            f"⏰ Payment link expires in 1 hour",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Pay Now", url=payment_info['pay_url'])],
                [InlineKeyboardButton(text="🔄 Check Payment", callback_data=f"check_payment_{payment.id}")]
            ]),
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            "❌ Failed to create payment. Please try again later."
        )
    
    await state.clear()

@dp.callback_query(F.data.startswith("check_payment_"))
async def check_payment_status(callback: CallbackQuery):
    """Check payment status"""
    payment_id = int(callback.data.replace("check_payment_", ""))
    
    async with get_db_context() as db:
        payment = await db.get(Payment, payment_id)
        if not payment:
            await callback.answer("Payment not found.")
            return
        
        if payment.payment_id:
            payment_info = await payment_processor.check_payment(payment.payment_id)
            
            if payment_info and payment_info["status"] == "paid":
                # Payment completed - activate subscription
                if await payment_processor.process_payment_webhook({
                    "invoice_id": payment.payment_id,
                    "payload": f'{{"payment_id": {payment_id}, "user_id": {payment.user_id}}}',
                    "status": "paid"
                }):
                    await callback.answer("Payment confirmed! Subscription activated.", show_alert=True)
                    await notification_service.send_payment_confirmation(
                        payment.user_id, 
                        payment.subscription
                    )
                else:
                    await callback.answer("Payment confirmed but activation failed. Contact support.", show_alert=True)
            else:
                await callback.answer(f"Payment status: {payment_info['status'] if payment_info else 'Unknown'}")
        else:
            await callback.answer("Payment not initiated properly.")

@dp.callback_query(F.data.startswith("change_protocol"))
async def change_protocol(callback: CallbackQuery):
    """Handle protocol change request"""
    await callback.message.edit_text(
        "Choose new protocol:",
        reply_markup=get_protocol_keyboard()
    )

@dp.callback_query(F.data.startswith("protocol_"))
async def process_protocol_change(callback: CallbackQuery):
    """Process protocol change"""
    if callback.message.text and "Choose new protocol" in callback.message.text:
        # This is a protocol change request
        new_protocol = callback.data.replace("protocol_", "")
        
        async with get_db_context() as db:
            user = await db.get(User, callback.from_user.id)
            
            # Get active subscription
            active_sub = None
            for sub in user.subscriptions:
                if sub.status == SubscriptionStatus.ACTIVE:
                    active_sub = sub
                    break
            
            if not active_sub:
                await callback.answer("No active subscription found.")
                return
            
            # Update in Marzban
            if user.marzban_username:
                success = await marzban_api.change_user_protocol(
                    user.marzban_username,
                    new_protocol
                )
                
                if success:
                    # Update database
                    active_sub.protocol = new_protocol
                    await db.commit()
                    
                    await callback.message.edit_text(
                        f"✅ Protocol changed to {new_protocol.upper()}!\n\n"
                        f"Please restart your VPN client to apply changes."
                    )
                else:
                    await callback.answer("Failed to change protocol. Contact support.", show_alert=True)
            else:
                await callback.answer("User not found in VPN system.", show_alert=True)
    else:
        await callback.answer("Invalid request.")

@dp.callback_query(F.data.startswith("renew_"))
async def renew_subscription(callback: CallbackQuery):
    """Handle subscription renewal"""
    subscription_id = int(callback.data.replace("renew_", "")) if callback.data.replace("renew_", "").isdigit() else None
    
    if subscription_id:
        # Renew specific subscription
        async with get_db_context() as db:
            subscription = await db.get(Subscription, subscription_id)
            if subscription and subscription.user_id == callback.from_user.id:
                await callback.message.edit_text(
                    f"🔄 **Renew Subscription**\n\n"
                    f"Current plan: {subscription.plan_name.replace('_', ' ').title()}\n"
                    f"Current price: ${subscription.price}\n\n"
                    f"Choose new plan:",
                    reply_markup=get_plans_keyboard()
                )
    else:
        # Start new purchase flow
        await callback.message.edit_text(
            "💰 Choose your subscription plan:",
            reply_markup=get_plans_keyboard()
        )

# Admin handlers
@dp.callback_query(F.data.startswith("admin_"))
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
        await admin_panel.show_user_details(callback, user_id)
    elif action.startswith("ban_"):
        user_id = int(action.split("_")[1])
        await admin_panel.ban_user(callback, user_id)
    elif action.startswith("unban_"):
        # Implement unban logic
        await callback.answer("Unban feature coming soon.")
    elif action.startswith("extend_"):
        subscription_id = int(action.split("_")[1])
        await admin_panel.extend_subscription(callback, subscription_id)
    elif action.startswith("extend_days_"):
        parts = action.split("_")
        subscription_id = int(parts[2])
        days = int(parts[3])
        await admin_panel.extend_subscription_days(callback, subscription_id, days)
    elif action.startswith("payments_"):
        if "_" in action:
            page_or_status = action.split("_")[1]
            if page_or_status.isdigit():
                await admin_panel.show_payments(callback, int(page_or_status))
            else:
                await admin_panel.show_payments(callback, 1, page_or_status)
        else:
            await admin_panel.show_payments(callback)
    elif action == "stats":
        await admin_panel.show_main_menu(callback.message)  # Detailed stats coming soon
    elif action == "broadcast":
        await callback.answer("Broadcast feature coming soon.")
    elif action == "settings":
        await callback.answer("Settings feature coming soon.")
    else:
        await callback.answer("Unknown action.")

@dp.message(F.text == "👥 Users")
async def admin_users(message: Message):
    """Handle admin users command"""
    if admin_panel.is_admin(message.from_user.id):
        await admin_panel.show_users(CallbackQuery(id="temp", message=message), 1)

@dp.message(F.text == "💳 Payments")
async def admin_payments(message: Message):
    """Handle admin payments command"""
    if admin_panel.is_admin(message.from_user.id):
        await admin_panel.show_payments(CallbackQuery(id="temp", message=message), 1)

@dp.message(F.text == "📊 Statistics")
async def admin_statistics(message: Message):
    """Handle admin statistics command"""
    if admin_panel.is_admin(message.from_user.id):
        await admin_panel.show_main_menu(message)

@dp.message(F.text == "📱 My Subscription")
async def my_subscription(message: Message):
    """Show user's subscription"""
    async with get_db_context() as db:
        user = await db.get(User, message.from_user.id)
        
        # Get active subscription
        active_sub = None
        for sub in user.subscriptions:
            if sub.status == SubscriptionStatus.ACTIVE:
                active_sub = sub
                break
        
        if not active_sub:
            await message.answer(
                "❌ You don't have an active subscription.\n"
                "Click '💰 Buy Subscription' to get started!"
            )
            return
        
        # Calculate remaining days
        remaining_days = (active_sub.expires_at - datetime.now()).days if active_sub.expires_at else 0
        
        text = (
            f"📱 **Your Subscription**\n\n"
            f"🔹 Plan: {active_sub.plan_name.replace('_', ' ').title()}\n"
            f"🔹 Protocol: {active_sub.protocol.upper()}\n"
            f"🔹 Status: {active_sub.status.title()}\n"
            f"🔹 Started: {active_sub.started_at.strftime('%Y-%m-%d') if active_sub.started_at else 'N/A'}\n"
            f"🔹 Expires: {active_sub.expires_at.strftime('%Y-%m-%d') if active_sub.expires_at else 'N/A'}\n"
            f"🔹 Remaining: {remaining_days} days\n\n"
        )
        
        if active_sub.subscription_url:
            text += f"🔗 **Subscription URL:**\n`{active_sub.subscription_url}`\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Change Protocol", callback_data="change_protocol")],
            [InlineKeyboardButton(text="🔗 Get Config", callback_data="get_config")],
            [InlineKeyboardButton(text="🔄 Renew", callback_data="renew_subscription")],
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.message(F.text == "🆘 Support")
async def support(message: Message, state: FSMContext):
    """Handle support request"""
    await message.answer(
        f"🆘 **Support**\n\n"
        f"You can contact our support team:\n"
        f"👤 @{settings.support_username}\n\n"
        f"Or describe your issue below and we'll forward it:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Main Menu")]],
            resize_keyboard=True
        )
    )
    await state.set_state(SupportStates.message)

@dp.message(SupportStates.message)
async def process_support_message(message: Message, state: FSMContext):
    """Process support message"""
    if message.text == "🔙 Main Menu":
        await state.clear()
        await message.answer("🔙 Main Menu", reply_markup=get_main_keyboard(message.from_user.id))
        return
    
    # Forward message to admin
    support_text = (
        f"🆘 **New Support Request**\n\n"
        f"👤 User: {message.from_user.full_name} (@{message.from_user.username})\n"
        f"🆔 ID: {message.from_user.id}\n\n"
        f"📝 Message:\n{message.text}"
    )
    
    try:
        await bot.send_message(settings.admin_id, support_text, parse_mode="Markdown")
        await message.answer("✅ Your message has been sent to our support team. We'll respond shortly.")
    except Exception as e:
        logger.error(f"Failed to forward support message: {e}")
        await message.answer("❌ Failed to send message. Please try again later.")
    
    await state.clear()
    await message.answer("🔙 Main Menu", reply_markup=get_main_keyboard(message.from_user.id))

@dp.message(F.text == "🔙 Main Menu")
async def main_menu(message: Message, state: FSMContext):
    """Return to main menu"""
    await state.clear()
    if message.from_user.id == settings.admin_id:
        await message.answer("🔙 Admin Menu", reply_markup=get_admin_keyboard())
    else:
        await message.answer("🔙 Main Menu", reply_markup=get_main_keyboard(message.from_user.id))

def get_duration_days(plan: str) -> int:
    """Get duration in days for a plan"""
    durations = {
        "1_month": 30,
        "3_months": 90,
        "6_months": 180,
        "1_year": 365
    }
    return durations.get(plan, 30)

async def main():
    """Main function to start the bot"""
    await init_db()
    logger.info("Database initialized")
    
    # Start notification service
    await notification_service.start()
    logger.info("Notification service started")
    
    logger.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
