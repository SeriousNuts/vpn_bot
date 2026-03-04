import logging

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)

from src.core.config import settings
from src.core.database import user_repo, subscription_repo, payment_repo
from src.enums import UserStatus, SubscriptionStatus
from src.models import Subscription
from src.services.marzban import marzban_service
from src.services.payment import payment_processor
from utils.format_error import format_error_traceback

logger = logging.getLogger(__name__)

# Create router
user_router = Router()

# States
class PurchaseStates(StatesGroup):
    plan = State()
    protocol = State()
    payment_method = State()

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

def get_plan_display_name(plan_key: str) -> str:
    """Возвращает отображаемое имя плана по ключу"""
    plan_names = {
        "1_month": "1 месяц",
        "3_months": "3 месяца", 
        "6_months": "6 месяцев",
        "1_year": "1 год"
    }
    return plan_names.get(plan_key, plan_key.replace('_', ' ').title())

def get_plans_keyboard() -> InlineKeyboardMarkup:
    """Формирует клавиатуру с планами из конфигурации"""
    buttons = []
    
    # Формируем кнопки из конфигурации
    for plan_key, price in settings.subscription_prices.items():
        plan_name = get_plan_display_name(plan_key)
        button_text = f"{plan_name} - ${price}"
        callback_data = f"plan_{plan_key}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
    
    # Добавляем кнопку "Назад"
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_payment_methods_keyboard() -> InlineKeyboardMarkup:
    """Формирует клавиатуру со способами оплаты"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="payment_stars")],
        [InlineKeyboardButton(text="💳 CryptoBot - USDT", callback_data="payment_cryptobot_usdt")],
        [InlineKeyboardButton(text="🔷 CryptoBot - TON", callback_data="payment_cryptobot_ton")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")],
    ])
    return keyboard

def get_protocol_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="VLESS", callback_data="protocol_vless")],
        [InlineKeyboardButton(text="VMESS", callback_data="protocol_vmess")],
        [InlineKeyboardButton(text="Trojan", callback_data="protocol_trojan")],
        [InlineKeyboardButton(text="Shadowsocks", callback_data="protocol_shadowsocks")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")],
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
        logger.error(f"Error in cmd_start: {format_error_traceback(e)}")
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
    
    plan_display_name = get_plan_display_name(plan)
    
    await state.update_data(plan=plan, price=price)
    
    await callback.message.edit_text(
        text=f"✅ Тариф выбран: {plan_display_name}\n💰 Цена: ${price}\n\nТеперь выберите предпочитаемый протокол:",
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
    
    # Сохраняем протокол в состояние
    await state.update_data(protocol=protocol)
    
    plan_display_name = get_plan_display_name(plan)
    
    await callback.message.edit_text(
        text=f"✅ Конфигурация выбрана:\n\n"
        f"📋 **Тариф:** {plan_display_name}\n"
        f"🔧 **Протокол:** {protocol.upper()}\n"
        f"� **Цена:** ${price}\n\n"
        f"Выберите способ оплаты:",
        reply_markup=get_payment_methods_keyboard()
    )
    await state.set_state(PurchaseStates.payment_method)

@user_router.callback_query(F.data == "payment_stars", PurchaseStates.payment_method)
async def process_payment_stars(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора оплаты через Telegram Stars"""
    data = await state.get_data()
    plan = data["plan"]
    protocol = data["protocol"]
    price = data["price"]
    
    user = await user_repo.get_user_by_telegram_id(callback.from_user.id)
    subscription = await subscription_repo.create_subscription(
        user_id=user.id,
        plan_name=plan,
        price=price,
        duration_days=get_duration_days(plan),
        status=SubscriptionStatus.PENDING,
        protocol=protocol
    )

    plan_display_name = get_plan_display_name(plan)
    
    # Create pending payment for stars
    payment = await payment_repo.create_payment(
        user_id=user.id,
        payment_id=None,  # Изначально None, обновится после успешной оплаты
        subscription_id=subscription.id,
        amount=price,
        payment_method="stars",
        description=f"VPN Подписка - {plan_display_name}"
    )

    
    # Перенаправляем на обработчик payment_stars
    from src.handlers.payment_stars import process_stars_payment
    await process_stars_payment(callback, payment, plan_display_name, protocol, price)
    
    await state.clear()

@user_router.callback_query(F.data == "payment_cryptobot_usdt", PurchaseStates.payment_method)
async def process_payment_cryptobot_usdt(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора оплаты через CryptoBot USDT"""
    data = await state.get_data()
    plan = data["plan"]
    protocol = data["protocol"]
    price = data["price"]
    
    user = await user_repo.get_user_by_telegram_id(callback.from_user.id)
    subscription = await subscription_repo.create_subscription(
        user_id=user.id,
        plan_name=plan,
        price=price,
        duration_days=get_duration_days(plan),
        status=SubscriptionStatus.PENDING,
        protocol=protocol
    )

    plan_display_name = get_plan_display_name(plan)
    
    # Create pending payment for cryptobot
    payment = await payment_repo.create_payment(
        user_id=user.id,
        payment_id=None,  # Изначально None, обновится после создания invoice
        subscription_id=subscription.id,
        amount=price,
        payment_method="cryptobot_usdt",
        description=f"VPN Подписка - {plan_display_name}"
    )

    
    # Create CryptoBot payment with USDT
    payment_info = await payment_processor.create_payment_usdt(
        amount=price,
        description=f"VPN Подписка - {plan_display_name}",
        user_id=callback.from_user.id,
        payment_id=payment.id
    )
    print(f"payment_info: {payment_info}")
    if payment_info and payment_info.get('ok') and payment_info.get('pay_url'):
            # Update payment with external ID
            if payment_info.get('invoice_id'):
                print(f"Updating payment {payment.id} with external ID {payment_info['invoice_id']}")
                await payment_repo.update_payment_status(
                    payment.id, 
                    "completed", 
                    payment_info["invoice_id"]
                )
                print(f"Payment {payment.id} updated successfully")
            else:
                print(f"No invoice_id in payment_info: {payment_info}")
            
            await callback.message.edit_text(
                f"✅ Конфигурация сохранена!\n\n"
                f"📋 **Детали заказа:**\n"
                f"Тариф: {plan_display_name}\n"
                f"Протокол: {protocol.upper()}\n"
                f"Цена: ${price}\n\n"
                f"💳 **Детали оплаты:**\n"
                f"ID платежа: #{payment.id}\n"
                f"Сумма: ${price} USDT\n"
                f"Способ: CryptoBot (USDT)\n\n"
                f"🔗 **Нажмите для оплаты:**\n"
                f"[Оплатить]({payment_info['pay_url']})\n\n"
                f"⏰ Ссылка на оплату истекает через 1 час",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Оплатить USDT", url=payment_info['pay_url'])],
                    [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment_{payment.id}")]
                ]),
                parse_mode="Markdown"
            )
    else:
        await callback.message.edit_text(
            "❌ Не удалось создать платеж. Попробуйте позже."
        )
    
    await state.clear()

@user_router.callback_query(F.data == "payment_cryptobot_ton", PurchaseStates.payment_method)
async def process_payment_cryptobot_ton(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора оплаты через CryptoBot TON"""
    data = await state.get_data()
    plan = data["plan"]
    protocol = data["protocol"]
    price = data["price"]
    
    user = await user_repo.get_user_by_telegram_id(callback.from_user.id)
    subscription = await subscription_repo.create_subscription(
        user_id=user.id,
        plan_name=plan,
        price=price,
        duration_days=get_duration_days(plan),
        status=SubscriptionStatus.PENDING,
        protocol=protocol
    )

    plan_display_name = get_plan_display_name(plan)
    
    # Create pending payment for cryptobot
    payment = await payment_repo.create_payment(
        user_id=user.id,
        payment_id=None,  # Изначально None, обновится после создания invoice
        subscription_id=subscription.id,
        amount=price,
        payment_method="cryptobot_ton",
        description=f"VPN Подписка - {plan_display_name}"
    )

    
    # Create CryptoBot payment with TON
    print(f"Creating TON payment with amount={price}, user_id={callback.from_user.id}, payment_id={payment.id}")
    
    try:
        payment_info = await payment_processor.create_payment_ton(
            amount=price,
            description=f"VPN Подписка - {plan_display_name}",
            user_id=callback.from_user.id,
            payment_id=payment.id
        )
        print(f"TON payment creation result: {payment_info}")
        
        if payment_info and payment_info.get('ok') and payment_info.get('pay_url'):
            # Update payment with external ID
            if payment_info.get('invoice_id'):
                print(f"Updating payment {payment.id} with external ID {payment_info['invoice_id']}")
                await payment_repo.update_payment_status(
                    payment.id, 
                    "completed", 
                    payment_info["invoice_id"]
                )
                print(f"Payment {payment.id} updated successfully")
            else:
                print(f"No invoice_id in payment_info: {payment_info}")
            
            await callback.message.edit_text(
                f"✅ Конфигурация сохранена!\n\n"
                f"📋 **Детали заказа:**\n"
                f"Тариф: {plan_display_name}\n"
                f"Протокол: {protocol.upper()}\n"
                f"Цена: ${price}\n\n"
                f"💳 **Детали оплаты:**\n"
                f"ID платежа: #{payment.id}\n"
                f"Сумма: ${price} (эквивалент в TON)\n"
                f"Способ: CryptoBot (TON)\n\n"
                f"🔗 **Нажмите для оплаты:**\n"
                f"[Оплатить]({payment_info['pay_url']})\n\n"
                f"⏰ Ссылка на оплату истекает через 1 час",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔷 Оплатить TON", url=payment_info['pay_url'])],
                    [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment_{payment.id}")]
                ]),
                parse_mode="Markdown"
            )
        else:
            print(f"Failed to create TON payment: {payment_info}")
            await callback.message.edit_text(
                "❌ Не удалось создать платеж. Попробуйте позже.\n\n"
                f"Детали ошибки: {payment_info if payment_info else 'No response from API'}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
                ])
            )
            
    except Exception as e:
        print(f"Exception during TON payment creation: {format_error_traceback(e)}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при создании платежа. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
            ])
        )
    
    await state.clear()

@user_router.callback_query(F.data.startswith("check_payment_"))
async def check_payment_status(callback: CallbackQuery):
    """Check payment status"""
    payment_id = int(callback.data.replace("check_payment_", ""))
    
    try:
        payment = await payment_repo.get_payment(payment_id)
        
        if not payment:
            logger.error(f"❌ Платеж не найден в БД: {payment_id}")
            await callback.answer("❌ Информация о платеже не найдена", show_alert=True)
            return
        
        # Логируем информацию о платеже для диагностики
        logger.info(f"🔍 Проверка платежа {payment_id}:")
        logger.info(f"  - payment_method: {payment.payment_method}")
        logger.info(f"  - payment_id (external): {payment.payment_id}")
        logger.info(f"  - status: {payment.status}")
        logger.info(f"  - subscription_id: {payment.subscription_id}")
        
        # Если есть внешний ID платежа, проверяем через CryptoBot API
        if payment.payment_id:
            payment_info = await payment_processor.check_payment(payment.payment_id)
            
            logger.info(f"  - payment_info from API: {payment_info}")
            
            if payment_info and payment_info.get("status") == "paid":
                logger.info(f"✅ Платеж {payment_id} оплачен, активируем подписку")
                # Активируем подписку
                success = await activate_subscription_after_payment(payment)
                
                if success:
                    await callback.message.edit_text(
                        "✅ **Платеж успешно получен!**\n\n"
                        "🎉 Ваша подписка активирована.\n"
                        "📱 Теперь вы можете использовать VPN сервис.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="📱 Моя подписка", callback_data="my_subscription")],
                            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="show_main_menu")]
                        ])
                    )
                    await callback.answer("✅ Платеж успешно обработан!")
                else:
                    await callback.answer("❌ Ошибка активации подписки",reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")]
                        ]))
            else:
                logger.warning(f"⚠️ Платеж {payment_id} еще не оплачен. Статус: {payment_info.get('status') if payment_info else 'Unknown'}")
                await callback.answer("🔄 Платеж еще не обработан", show_alert=True)
        else:
            logger.warning(f"⚠️ У платежа {payment_id} нет внешнего ID, метод: {payment.payment_method}")
            
            # Для платежей через Stars обрабатываем по-другому
            if payment.payment_method == "stars":
                logger.info(f"🔄 Проверяем статус платежа Stars: {payment_id}")
                # Здесь может быть дополнительная логика для Stars
                await callback.answer("🔄 Проверка статуса платежа Stars...", show_alert=True)
            # Для платежей через CryptoBot (USDT и TON)
            elif payment.payment_method in ["cryptobot_usdt", "cryptobot_ton"]:
                logger.info(f"🔄 Проверяем статус платежа CryptoBot: {payment_id}")
                await callback.answer("🔄 Проверка статуса платежа CryptoBot...", show_alert=True)
            else:
                logger.error(f"❌ Неизвестный метод оплаты: {payment.payment_method}")
                await callback.answer("❌ Неизвестный метод оплаты", show_alert=True)
                
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке платежа {payment_id}: {format_error_traceback(e)}")
        await callback.answer("❌ Ошибка при проверке платежа", show_alert=True)

async def activate_subscription_after_payment(payment) -> bool:
    """Активация подписки после успешной оплаты"""
    try:
        # Получаем информацию о подписке
        subscription = await subscription_repo.db.get_by_id(Subscription, payment.subscription_id)
        if not subscription:
            logger.error(f"❌ Подписка не найдена: {payment.subscription_id}")
            return False
        
        # Активируем подписку в Marzban
        user = await user_repo.get_user_by_id(payment.user_id)
        marzban_user = await marzban_service.create_user(
            user=user,
            subscription=subscription
        )

        
        # Обновляем статус подписки
        await subscription_repo.update_subscription_status(
            subscription.id, 
            SubscriptionStatus.ACTIVE
        )
        if not marzban_user:
            logger.error("Не удалось создать пользователя в marzban")
            return False
        logger.info(f"✅ Подписка активирована: {subscription.id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка активации подписки: {format_error_traceback(e)}")
        return False

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
            f"🔐 Статус {active_sub.status}\n\n"
            f"📦 Тариф: {active_sub.plan_name.replace('_', ' ').title()}\n"
            f"💰 Цена: ${active_sub.price}\n"
            f"⏱️ Длительность: {active_sub.duration_days} дней\n"
            f"🔗 Протокол: {active_sub.protocol.upper()}\n"
            f"📅 Статус: {active_sub.status}\n"
            f"⏳ Осталось: {remaining_days} дней\n\n"
            f"Ссылка для подписки <code>{active_sub.subscription_url}</code>\n\n"
            f"ID пользователя: <code>{message.from_user.id}</code>\n"
            f"ID подписки <code>{active_sub.id}</code>\n"
        )
        
        if active_sub.expires_at:
            subscription_text += f"\n🗓️ Истекает: {active_sub.expires_at.strftime('%Y-%m-%d %H:%M')}\n"
        
        await message.answer(subscription_text)
        
    except Exception as e:
        logger.error(f"Error in my_subscription: {format_error_traceback(e)}")
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
    if message.text == "🔙 Главное меню":
        await state.clear()
        await message.answer("🔙 Главное меню", reply_markup=get_main_keyboard())
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
        print(f"Failed to forward support message: {format_error_traceback(e)}")
        await message.answer("❌ Failed to send message. Please try again later.")
    
    await state.clear()
    await message.answer("🔙 Главное меню", reply_markup=get_main_keyboard())

@user_router.message(F.text == "🔙 Главное меню")
async def main_menu(message: Message, state: FSMContext):
    """Return to 🔙 Главное меню"""
    await state.clear()
    await message.answer("🔙 Главное меню", reply_markup=get_main_keyboard())
