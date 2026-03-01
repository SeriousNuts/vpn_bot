import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)

from src.core.config import settings
from src.core.database import user_repo, subscription_repo, payment_repo, notification_repo
from src.enums import UserStatus, SubscriptionStatus
from src.models import User, Subscription, Payment
from src.services.notification import notification_service
from src.services.payment import payment_processor

logger = logging.getLogger(__name__)

# Create router
user_router = Router()

# States
class PurchaseStates(StatesGroup):
    plan = State()
    protocol = State()

class SupportStates(StatesGroup):
    message = State()

# Keyboards
def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Моя подписка")],
            [KeyboardButton(text="💰 Купить подписку")],
            [KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="🆘 Поддержка")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

def get_plans_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 месяц - $10", callback_data="plan_1_month")],
        [InlineKeyboardButton(text="3 месяца - $25", callback_data="plan_3_months")],
        [InlineKeyboardButton(text="6 месяцев - $45", callback_data="plan_6_months")],
        [InlineKeyboardButton(text="1 год - $80", callback_data="plan_1_year")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")],
    ])
    return keyboard

def get_protocol_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="VLESS", callback_data="protocol_vless")],
        [InlineKeyboardButton(text="VMESS", callback_data="protocol_vmess")],
        [InlineKeyboardButton(text="Trojan", callback_data="protocol_trojan")],
        [InlineKeyboardButton(text="Shadowsocks", callback_data="protocol_shadowsocks")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")],
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
    
    try:
        # Check if user exists
        user = await user_repo.get_user_by_telegram_id(message.from_user.id)
        
        if not user:
            # Create new user
            await user_repo.create_user(
                telegram_id=message.from_user.id,
                status=UserStatus.ACTIVE
            )
            
            welcome_text = (
                f"🎉 Добро пожаловать в VPN Bot!\n\n"
                f"Выберите опцию для начала работы:"
            )
            
            keyboard = get_main_keyboard()
            await message.answer(welcome_text, reply_markup=keyboard)
        else:
            # Existing user
            if message.from_user.id == settings.admin_id:
                from src.handlers.admin import get_admin_keyboard
                keyboard = get_admin_keyboard()
                await message.answer("👋 Добро пожаловать, Администратор!", reply_markup=keyboard)
            else:
                keyboard = get_main_keyboard()
                await message.answer(f"👋 С возвращением!", reply_markup=keyboard)
                
    except Exception as e:
        logger.error(f"Error in cmd_start: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")

@user_router.message(F.text == "💰 Купить подписку")
async def buy_subscription(message: Message, state: FSMContext):
    """Handle buy subscription"""
    await message.answer(
        "💰 Выберите тарифный план:",
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
        f"✅ Тариф выбран: {plan.replace('_', ' ').title()}\n"
        f"💰 Цена: ${price}\n\n"
        "Теперь выберите предпочитаемый протокол:",
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
    user = await user_repo.get_user_by_telegram_id(callback.from_user.id)

    subscription = Subscription(
        user_id=user.id,
        plan_name=plan,
        price=price,
        duration_days=get_duration_days(plan),
        status=SubscriptionStatus.PENDING,
        protocol=protocol
    )
    await subscription_repo.create_subscription(subscription=subscription)


    # Create pending payment
    pending_payment = Payment(
        user_id=user.id,
        subscription_id=subscription.id,
        amount=price,
        payment_method="cryptobot",
        description=f"VPN Подписка - {plan.replace('_', ' ').title()}"
    )
    payment = await payment_repo.create_payment(pending_payment)

    
    # Create CryptoBot payment
    payment_info = await payment_processor.create_payment(
        amount=price,
        description=f"VPN Подписка - {plan.replace('_', ' ').title()}",
        user_id=callback.from_user.id,
        payment_id=payment.id
    )
    
    if payment_info:
        # Update payment with external ID
        payment = await payment_repo.get_payment(payment.id)
        payment.payment_id = payment_info["invoice_id"]
        await payment_repo.update_payment(payment)

        
        await callback.message.edit_text(
            f"✅ Конфигурация сохранена!\n\n"
            f"📋 **Детали заказа:**\n"
            f"Тариф: {plan.replace('_', ' ').title()}\n"
            f"Протокол: {protocol.upper()}\n"
            f"Цена: ${price}\n\n"
            f"💳 **Детали оплаты:**\n"
            f"ID платежа: #{payment.id}\n"
            f"Сумма: ${price} USDT\n\n"
            f"🔗 **Нажмите для оплаты:**\n"
            f"[Оплатить]({payment_info['pay_url']})\n\n"
            f"⏰ Ссылка на оплату истекает через 1 час",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=payment_info['pay_url'])],
                [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment_{payment.id}")]
            ]),
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            "❌ Не удалось создать платеж. Попробуйте позже."
        )
    
    await state.clear()

@user_router.callback_query(F.data.startswith("check_payment_"))
async def check_payment_status(callback: CallbackQuery):
    """Check payment status"""
    payment_id = int(callback.data.replace("check_payment_", ""))
    payment = await payment_repo.get_payment(payment_id)

    if payment.payment_id:
        payment_info = await payment_processor.check_payment(payment.payment_id)

        if payment_info and payment_info["status"] == "paid":
            # Payment completed - activate subscription
            if await payment_processor.process_payment_webhook({
                "invoice_id": payment.payment_id,
                "payload": f'{{"payment_id": {payment_id}, "user_id": {payment.user_id}}}',
                "status": "paid"
            }):
                await callback.answer("Оплата подтверждена! Подписка активирована.", show_alert=True)
                await notification_service.send_payment_confirmation(
                    payment.user_id,
                    payment.subscription
                )
            else:
                await callback.answer("Оплата подтверждена, но активация не удалась. Свяжитесь с поддержкой.", show_alert=True)
        else:
            await callback.answer(f"Статус оплаты: {payment_info['status'] if payment_info else 'Неизвестно'}")
    else:
        await callback.answer("Платеж не инициирован корректно.")

@user_router.message(F.text == "📱 Моя подписка")
async def my_subscription(message: Message):
    """Show user's subscription"""
    try:
        # Get user with subscriptions
        user = await user_repo.get_user_with_subscriptions(message.from_user.id)
        
        if not user:
            await message.answer(
                "❌ Пользователь не найден. Перезапустите бота командой /start"
            )
            return
        
        # Get active subscription
        active_sub = await subscription_repo.get_active_subscription(user.id)
        
        if not active_sub:
            await message.answer(
                "❌ У вас нет активной подписки.\n"
                "Нажмите '💰 Купить подписку' для начала!"
            )
            return
        
        # Calculate remaining days
        from datetime import datetime
        if active_sub.expires_at:
            remaining_days = (active_sub.expires_at - datetime.now()).days
            remaining_days = max(0, remaining_days)
        else:
            remaining_days = 0
        
        subscription_text = (
            f"📱 **Ваша подписка**\n\n"
            f"📦 Тариф: {active_sub.plan_name.replace('_', ' ').title()}\n"
            f"💰 Цена: ${active_sub.price}\n"
            f"⏱️ Длительность: {active_sub.duration_days} дней\n"
            f"🔗 Протокол: {active_sub.protocol.upper()}\n"
            f"📅 Статус: {active_sub.status}\n"
            f"⏳ Осталось: {remaining_days} дней\n"
        )
        
        if active_sub.expires_at:
            subscription_text += f"\n🗓️ Истекает: {active_sub.expires_at.strftime('%Y-%m-%d %H:%M')}\n"
        
        # Add VPN configuration if active
        if active_sub.status == SubscriptionStatus.ACTIVE and active_sub.marzban_username:
            subscription_text += f"\n🔐 VPN Имя пользователя: {active_sub.marzban_username}\n"
        
        await message.answer(subscription_text)
        
    except Exception as e:
        logger.error(f"Error in my_subscription: {e}")
        await message.answer("❌ Не удалось загрузить информацию о подписке.")

@user_router.message(F.text == "🆘 Поддержка")
async def support(message: Message, state: FSMContext):
    """Handle support request"""
    await message.answer(
        f"🆘 **Поддержка**\n\n"
        f"Вы можете связаться с нашей командой поддержки:\n"
        f"👤 @{settings.support_username}\n\n"
        f"Или опишите вашу проблему ниже, и мы пересылем ее:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Главное меню")]],
            resize_keyboard=True
        )
    )
    await state.set_state(SupportStates.message)

@user_router.message(SupportStates.message)
async def process_support_message(message: Message, state: FSMContext):
    """Process support message"""
    if message.text == "🔙 Main Menu":
        await state.clear()
        await message.answer("🔙 Main Menu", reply_markup=get_main_keyboard())
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
    await message.answer("🔙 Main Menu", reply_markup=get_main_keyboard())

@user_router.message(F.text == "🔙 Main Menu")
async def main_menu(message: Message, state: FSMContext):
    """Return to main menu"""
    await state.clear()
    await message.answer("🔙 Main Menu", reply_markup=get_main_keyboard())
