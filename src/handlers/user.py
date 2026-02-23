from typing import Dict, Any
from datetime import datetime, timedelta
from aiogram import Router, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.core.config import settings
from src.core.database import get_db_context
from src.models import User, Subscription, Payment
from src.enums import UserStatus, SubscriptionStatus, PaymentStatus, ProtocolType
from src.services.payment import payment_processor
from src.services.notification import notification_service

# Create router
user_router = Router()

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

def get_duration_days(plan: str) -> int:
    """Get duration in days for a plan"""
    durations = {
        "1_month": 30,
        "3_months": 90,
        "6_months": 180,
        "1_year": 365
    }
    return durations.get(plan, 30)

# Handlers
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
            
            keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="📱 Share Phone", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await message.answer(welcome_text, reply_markup=keyboard)
            await state.set_state(RegistrationStates.phone)
        else:
            # Existing user
            keyboard = get_main_keyboard(message.from_user.id)
            await message.answer("👋 Welcome back!", reply_markup=keyboard)

@user_router.message(F.contact, RegistrationStates.phone)
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

@user_router.message(RegistrationStates.email)
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

@user_router.message(F.text == "💰 Buy Subscription")
async def buy_subscription(message: Message, state: FSMContext):
    """Handle buy subscription"""
    await message.answer(
        "💰 Choose your subscription plan:",
        reply_markup=get_plans_keyboard()
    )
    await state.set_state(PurchaseStates.plan)

@user_router.callback_query(F.data.startswith("plan_"), PurchaseStates.plan)
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

@user_router.callback_query(F.data.startswith("protocol_"), PurchaseStates.protocol)
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

@user_router.callback_query(F.data.startswith("check_payment_"))
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

@user_router.message(F.text == "📱 My Subscription")
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

@user_router.message(F.text == "🆘 Support")
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

@user_router.message(SupportStates.message)
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
        from src.bot import bot
        await bot.send_message(settings.admin_id, support_text, parse_mode="Markdown")
        await message.answer("✅ Your message has been sent to our support team. We'll respond shortly.")
    except Exception as e:
        print(f"Failed to forward support message: {e}")
        await message.answer("❌ Failed to send message. Please try again later.")
    
    await state.clear()
    await message.answer("🔙 Main Menu", reply_markup=get_main_keyboard(message.from_user.id))

@user_router.message(F.text == "🔙 Main Menu")
async def main_menu(message: Message, state: FSMContext):
    """Return to main menu"""
    await state.clear()
    await message.answer("🔙 Main Menu", reply_markup=get_main_keyboard(message.from_user.id))
