"""
Обновленные пользовательские хендлеры с интеграцией платежей через Telegram Stars
"""

import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.core.config import settings
from src.core.database import user_repo, subscription_repo, payment_repo
from src.enums import SubscriptionStatus
from src.handlers.payment_integration import update_main_keyboard_with_payments
from src.handlers.payment_stars import process_stars_payment
from src.services.marzban import marzban_service
from src.services.payment import payment_processor
from utils.format_error import format_error_traceback


# Импортируем функцию для клавиатуры планов
def get_plans_keyboard():
    """Формирует клавиатуру с тарифными планами"""

    buttons = []
    for plan_key, price in settings.subscription_prices.items():
        plan_name = {
            "1_month": "1 месяц",
            "3_months": "3 месяца", 
            "6_months": "6 месяцев",
            "1_year": "1 год"
        }.get(plan_key, plan_key.replace('_', ' ').title())
        
        button_text = f"{plan_name} - ${price}"
        callback_data = f"plan_{plan_key}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
    
    # Добавляем кнопку "Назад"
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

logger = logging.getLogger(__name__)

# Создаем роутер
user_router = Router()


async def get_back_to_main_inline_keyboard() -> InlineKeyboardMarkup:
    """
    Создание inline клавиатуры для возврата в главное меню
    
    Returns:
        InlineKeyboardMarkup с кнопкой возврата
    """

    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="show_main_menu"
        )
    )
    return builder.as_markup()


async def get_main_keyboard():
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
            await user_repo.create_user(
                telegram_id=message.from_user.id,
            )
            
            welcome_text = (
                f"🎉 <b>Добро пожаловать {user.telegram_id} в VPN Bot!</b>\n\n"
                "🚀 Я помогу вам получить доступ к безопасному и быстрому интернету.\n\n"
                "💡 <b>Что я могу делать:</b>\n"
                "• 📱 Управлять вашей VPN подпиской\n"
                "• 💎 Принимать оплату через Telegram Stars и cryptoBOT\n"
                "• 📊 Показывать статистику использования\n"
                "• 💬 Даже есть поддержка\n\n"
                "🎯 <b>Начните с выбора тарифа:</b>"
            )
        else:
            welcome_text = (
                f"👋 <b>С возвращением, tg_{user.telegram_id or 'пользователь'}!</b>\n\n"
                "🚀 Готов помочь вам с VPN подпиской.\n\n"
                "💡 <b>Доступные действия:</b>\n"
                "• 📱 Посмотреть текущую подписку\n"
                "• 💎 Купить новую подписку\n"
                "• 💳 История платежей\n"
                "• 📊 Статистика использования\n\n"
                "🎯 <b>Выберите действие:</b>"
            )
        
        # Создаем клавиатуру
        keyboard = await get_main_keyboard()
        
        await message.answer(
            welcome_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"[START-999] Ошибка в команде /start: {format_error_traceback(e)}")
        await message.answer(
            "❌ [START-999] Произошла ошибка. Пожалуйста, попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


@user_router.message(F.text == "🏠 Главное меню")
async def cmd_main_menu(message: Message):
    """
    Обработчик кнопки "Главное меню"
    """
    try:
        keyboard = await get_main_keyboard()
        
        await message.answer(
            "🏠 **Главное меню**\n\n"
            "Выберите действие:",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"[MENU-999] Ошибка в главном меню: {format_error_traceback(e)}")
        await message.answer(
            "❌ [MENU-999] Произошла ошибка. Попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


@user_router.message(F.text == "💎 Купить подписку")
async def cmd_buy_subscription(message: Message):
    """
    Обработчик кнопки "Купить подписку"
    """
    try:
        # Прямо показываем выбор тарифов без FSM
        await message.answer(
            "💰 Выберите тарифный план:",
            reply_markup=get_plans_keyboard()
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в покупке подписки: {format_error_traceback(e)}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


@user_router.message(F.text == "💰 Купить подписку")
async def cmd_buy_subscription_alt(message: Message):
    """
    Обработчик кнопки "Купить подписку" (альтернативный)
    """
    try:
        # Прямо показываем выбор тарифов без FSM
        await message.answer(
            "💰 Выберите тарифный план:",
            reply_markup=get_plans_keyboard()
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в покупке подписки: {format_error_traceback(e)}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


@user_router.callback_query(F.data.startswith("plan_"))
async def process_plan_selection(callback: CallbackQuery):
    """Обработка выбора тарифного плана"""
    try:
        plan = callback.data.replace("plan_", "")
        
        # Импортируем настройки
        from src.core.config import settings
        usdt_prices = settings.get_prices_for_payment_method("cryptobot_usdt")
        price = usdt_prices[plan]
        
        plan_display_name = {
            "1_month": "1 месяц",
            "3_months": "3 месяца", 
            "6_months": "6 месяцев",
            "1_year": "1 год"
        }.get(plan, plan.replace('_', ' ').title())
        
        # Показываем выбор протокола с описаниями
        protocol_text = (
            f"✅ Тариф выбран: {plan_display_name}\n"
            f"💰 Цена: ${price}\n\n"
            f"🔧 <b>Выберите протокол подключения:</b>\n\n"
            f"📋 <b>Описания протоколов:</b>\n\n"
            f"🔹 <b>VLESS</b> - Современный протокол от V2Ray\n"
            f"   • Высокая скорость и стабильность\n"
            f"   • Минимальный overhead\n"
            f"   • Лучший выбор для большинства устройств\n\n"
            f"🔹 <b>VMESS</b> - Классический протокол V2Ray\n"
            f"   • Широкая совместимость\n"
            f"   • Надежная работа в любых условиях\n"
            f"   • Поддержка старых клиентов\n\n"
            f"🔹 <b>Trojan</b> - Протокол disguised под HTTPS\n"
            f"   • Максимальная скрытность трафика\n"
            f"   • Легко обходит блокировки\n"
            f"   • Идеален для restrictive сетей\n\n"
            f"🔹 <b>Shadowsocks</b> - Легкий прокси-протокол\n"
            f"   • Очень быстрый и легкий\n"
            f"   • Низкое потребление ресурсов\n"
            f"   • Хорош для слабых устройств\n\n"
            f"💡 <b>Важно:</b> Протокол можно будет сменить в любой момент через настройки подписки\n\n"
            f"👇 <b>Выберите протокол:</b>"
        )
        
        await callback.message.edit_text(
            text=protocol_text,
            reply_markup=get_protocol_keyboard()
        )
        
    except Exception as e:
        logger.error(f"[PLAN-999] Ошибка в выборе плана: {format_error_traceback(e)}")
        await callback.answer("❌ [PLAN-999] Произошла ошибка", show_alert=True)


def get_protocol_keyboard():
    """Формирует клавиатуру с выбором протокола"""
    
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


@user_router.callback_query(F.data.startswith("protocol_"))
async def process_protocol_selection(callback: CallbackQuery):
    """Обработка выбора протокола"""
    try:
        protocol = callback.data.replace("protocol_", "")
        
        protocol_info = {
            "vless": {
                "name": "VLESS",
                "description": "Современный быстрый протокол",
                "emoji": "🚀"
            },
            "vmess": {
                "name": "VMESS", 
                "description": "Классический надежный протокол",
                "emoji": "🛡️"
            },
            "trojan": {
                "name": "Trojan",
                "description": "Максимально скрытный протокол",
                "emoji": "🕵️"
            },
            "shadowsocks": {
                "name": "Shadowsocks",
                "description": "Легкий и быстрый прокси",
                "emoji": "⚡"
            }
        }
        
        selected = protocol_info.get(protocol, {"name": protocol.upper(), "description": "Выбранный протокол", "emoji": "🔧"})
        
        # Показываем выбор способа оплаты с подтверждением протокола
        await callback.message.edit_text(
            text=f"✅ <b>Конфигурация выбрана:</b>\n\n"
            f"{selected['emoji']} <b>Протокол:</b> {selected['name']}\n"
            f"📝 {selected['description']}\n\n"
            f"💡 <b>Напоминание:</b> Вы сможете сменить протокол в любой момент через настройки подписки\n\n"
            f"💳 <b>Выберите способ оплаты:</b>",
            reply_markup=get_payment_methods_keyboard()
        )
        
    except Exception as e:
        logger.error(f"[PROTO-999] Ошибка в выборе протокола: {format_error_traceback(e)}")
        await callback.answer("❌ [PROTO-999] Произошла ошибка", show_alert=True)


def get_payment_methods_keyboard():
    """Формирует клавиатуру со способами оплаты"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="payment_stars")],
        [InlineKeyboardButton(text="💳 CryptoBot - USDT", callback_data="payment_cryptobot_usdt")],
        [InlineKeyboardButton(text="🔷 CryptoBot - TON", callback_data="payment_cryptobot_ton")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")],
    ])
    return keyboard


@user_router.callback_query(F.data == "payment_stars")
async def process_payment_stars(callback: CallbackQuery):
    """Обработка выбора оплаты через Telegram Stars"""
    try:
        # Создаем временный payment объект для совместимости
        class TempPayment:
            def __init__(self):
                self.id = 1
                self.subscription = None
        
        payment = TempPayment()
        await process_stars_payment(callback, payment, "VPN подписка", "vless")
        
    except Exception as e:
        logger.error(f"[STARS-999] Ошибка в оплате звездами: {format_error_traceback(e)}")
        await callback.answer("❌ [STARS-999] Произошла ошибка", show_alert=True)


@user_router.callback_query(F.data == "payment_cryptobot_usdt")
async def process_payment_cryptobot_usdt(callback: CallbackQuery):
    """Обработка выбора оплаты через CryptoBot USDT"""
    try:
        logger.info(f"[USDT-001] Starting USDT payment process for user {callback.from_user.id}")

        # Получаем данные из callback (сохраняем в контексте сообщения)
        # В реальном приложении нужно сохранять данные о тарифе и протоколе
        # Для примера используем значения по умолчанию
        plan = "1_month"  # Можно получить из контекста или предыдущих шагов
        protocol = "vless"
        price = 5.0  # Можно получить из настроек
        
        logger.info(f"[USDT-002] Payment details: plan={plan}, protocol={protocol}, price={price}")
        
        # Получаем пользователя
        logger.info(f"[USDT-003] Getting user {callback.from_user.id}")
        user = await user_repo.get_user_by_telegram_id(callback.from_user.id)
        if not user:
            logger.error(f"[USDT-004] User {callback.from_user.id} not found")
            await callback.answer("❌ [USDT-004] Пользователь не найден", show_alert=True)
            return
        
        logger.info(f"[USDT-005] User found: {user.id}")
        
        # Создаем подписку
        logger.info("[USDT-006] Creating subscription")
        logger.info(f"user is {user.__dict__}")
        subscription = await subscription_repo.create_subscription(
            user_id=user.id,
            plan_name=plan,
            price=price,
            duration_days=30,  # Для 1 месяца
            status=SubscriptionStatus.PENDING,
            protocol=protocol
        )
        
        if not subscription:
            logger.error("[USDT-007] Failed to create subscription")
            await callback.message.edit_text(
                "❌ [USDT-007] Не удалось создать подписку. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
                ])
            )
            return
        
        logger.info(f"[USDT-008] Subscription created: {subscription.id}")
        
        plan_display_name = "1 месяц"
        
        # Создаем платеж в базе данных
        logger.info("[USDT-009] Creating payment record")
        payment = await payment_repo.create_payment(
            user_id=user.id,
            payment_id=None,  # Обновится после создания invoice
            subscription_id=subscription.id,
            amount=price,
            payment_method="cryptobot_usdt",
            description=f"VPN Подписка - {plan_display_name}"
        )
        
        if not payment:
            logger.error("[USDT-010] Failed to create payment record")
            await callback.message.edit_text(
                "❌ [USDT-010] Не удалось создать запись о платеже. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
                ])
            )
            return
        
        logger.info(f"[USDT-011] Payment record created: {payment.id}")
        
        # Создаем платеж через CryptoBot
        logger.info("[USDT-012] Creating CryptoBot invoice")
        payment_info = await payment_processor.create_payment_usdt(
            amount=price,
            description=f"VPN Подписка - {plan_display_name}",
            user_id=user.id,
            payment_id=payment.id
        )
        
        logger.info(f"[USDT-013] USDT Payment info: {payment_info}")
        
        # Проверяем успешное создание платежа
        if payment_info and payment_info.get('pay_url'):
            logger.info("[USDT-014] Payment invoice created successfully")
            
            # Обновляем платеж с внешним ID
            if payment_info.get('invoice_id'):
                logger.info(f"[USDT-015] Updating payment with invoice_id: {payment_info['invoice_id']}")
                await payment_repo.update_payment_status(
                    payment.id, 
                    "pending",  # Не completed, а pending т.к. Оплата еще не прошла
                    payment_info["invoice_id"]
                )
                logger.info("[USDT-016] Payment updated successfully")
            
            await callback.message.edit_text(
                f"✅ Конфигурация сохранена!\n\n"
                f"📋 <b>Детали заказа:</b>\n"
                f"Тариф: {plan_display_name}\n"
                f"Протокол: {protocol.upper()}\n"
                f"Цена: ${price}\n\n"
                f"💳 <b>Детали оплаты:</b>\n"
                f"ID платежа: #{payment.id}\n"
                f"Способ оплаты: USDT\n\n"
                f"🔗 <b>Ссылка для оплаты:</b>\n"
                f"<a href=\"{payment_info['pay_url']}\">Оплатить USDT</a>\n\n"
                f"⏰ Оплата будет обработана автоматически после поступления средств",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Оплатить", url=payment_info['pay_url'])],
                    [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_usdt_payment_{payment.id}")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
                ]),
                parse_mode="HTML"
            )
            logger.info("[USDT-017] Payment message sent to user")
        else:
            logger.error(f"[USDT-018] CryptoBot invoice creation failed: {payment_info}")
            await callback.message.edit_text(
                "❌ [USDT-018] Не удалось создать инвойс в CryptoBot. Попробуйте другой способ оплаты.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
                ])
            )
        
    except Exception as e:
        logger.error(f"[USDT-999] Критическая ошибка в оплате USDT: {format_error_traceback(e)}")
        await callback.message.edit_text(
            "❌ [USDT-999] Произошла критическая ошибка при обработке платежа. Пожалуйста, свяжитесь с поддержкой.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
            ])
        )


@user_router.callback_query(F.data == "payment_cryptobot_ton")
async def process_payment_cryptobot_ton(callback: CallbackQuery):
    """Обработка выбора оплаты через CryptoBot TON"""
    try:
        logger.info(f"[TON-001] Starting TON payment process for user {callback.from_user.id}")
        
        # Получаем данные из callback (сохраняем в контексте сообщения)
        # В реальном приложении нужно сохранять данные о тарифе и протоколе
        # Для примера используем значения по умолчанию
        plan = "1_month"  # По умолчанию
        protocol = "vless"  # По умолчанию
        
        from src.core.config import settings
        ton_prices = settings.get_prices_for_payment_method("cryptobot_ton")
        price = ton_prices[plan]
        
        plan_display_name = {
            "1_month": "1 месяц",
            "3_months": "3 месяца", 
            "6_months": "6 месяцев",
            "1_year": "1 год"
        }.get(plan, plan.replace('_', ' ').title())
        
        # Получаем пользователя
        logger.info(f"[TON-002] Getting user {callback.from_user.id}")
        user = await user_repo.get_user_by_telegram_id(callback.from_user.id)
        
        if not user:
            logger.error(f"[TON-003] User {callback.from_user.id} not found")
            await callback.message.edit_text(
                "❌ [TON-003] Пользователь не найден. Попробуйте перезапустить бота.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
                ])
            )
            return
        
        logger.info(f"[TON-004] User found: {user.__dict__}")
        
        # Создаем подписку
        logger.info("[TON-005] Creating subscription")
        subscription = await subscription_repo.create_subscription(
            user_id=user.id,
            plan_name=plan,
            price=price,
            duration_days=get_duration_days(plan),
            status=SubscriptionStatus.PENDING,
            protocol=protocol
        )
        
        if not subscription:
            logger.error("[TON-006] Failed to create subscription")
            await callback.message.edit_text(
                "❌ [TON-006] Не удалось создать подписку. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="� Назад", callback_data="show_main_menu")]
                ])
            )
            return
        
        logger.info(f"[TON-007] Subscription created: {subscription.id}")
        
        # Создаем запись о платеже
        logger.info("[TON-008] Creating payment record")
        payment = await payment_repo.create_payment(
            user_id=user.id,
            amount=price,
            currency="TON",
            payment_method="cryptobot_ton",
            subscription_id=subscription.id,
            description=f"VPN Подписка - {plan_display_name}"
        )
        
        if not payment:
            logger.error("[TON-009] Failed to create payment record")
            await callback.message.edit_text(
                "❌ [TON-009] Не удалось создать запись о платеже. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
                ])
            )
            return
        
        logger.info(f"[TON-010] Payment created: {payment.id}")
        
        # Создаем платеж через CryptoBot
        logger.info("[TON-011] Creating CryptoBot TON invoice")
        payment_info = await payment_processor.create_payment_ton(
            amount=price,
            description=f"VPN Подписка - {plan_display_name}",
            user_id=user.id,
            payment_id=payment.id
        )
        
        logger.info(f"[TON-012] CryptoBot response: {payment_info}")
        
        if payment_info and payment_info.get('pay_url'):
            # Обновляем платеж с внешним ID
            if payment_info.get('invoice_id'):
                logger.info(f"[TON-013] Updating payment with invoice_id: {payment_info['invoice_id']}")
                await payment_repo.update_payment_status(
                    payment.id, 
                    "pending",  # Не completed, а pending т.к. Оплата еще не прошла
                    payment_info["invoice_id"]
                )
                logger.info("[TON-014] Payment updated successfully")
            
            await callback.message.edit_text(
                f"✅ Конфигурация сохранена!\n\n"
                f"📋 <b>Детали заказа:</b>\n"
                f"Тариф: {plan_display_name}\n"
                f"Протокол: {protocol.upper()}\n"
                f"Цена: ${price}\n\n"
                f"💳 <b>Детали оплаты:</b>\n"
                f"ID платежа: #{payment.id}\n"
                f"Способ оплаты: TON\n\n"
                f"<a href=\"{payment_info['pay_url']}\">Оплатить TON</a>\n\n"
                f"⏰ Оплата будет обработана автоматически после поступления средств",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔷 Оплатить", url=payment_info['pay_url'])],
                    [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment_{payment.id}")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
                ]),
                parse_mode="HTML"
            )
        else:
            logger.error(f"[TON-015] CryptoBot invoice creation failed: {payment_info}")
            await callback.message.edit_text(
                "❌ [TON-015] Не удалось создать инвойс в CryptoBot. Попробуйте другой способ оплаты.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
                ])
            )
    except Exception as e:
        logger.error(f"[TON-999] Критическая ошибка в оплате TON: {format_error_traceback(e)}")
        await callback.message.edit_text(
            "❌ [TON-999] Произошла критическая ошибка при обработке платежа. Пожалуйста, свяжитесь с поддержкой.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
            ])
        )


@user_router.callback_query(F.data.startswith("check_payment_"))
async def check_payment_status(callback: CallbackQuery):
    """Check payment status"""
    payment_id = int(callback.data.replace("check_payment_", ""))
    
    try:
        payment = await payment_repo.get_payment(payment_id)
        
        if not payment:
            logger.error(f"[USER-005] Платеж не найден в БД: {payment_id}")
            await callback.answer("❌ [USER-005] Информация о платеже не найдена", show_alert=True)
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
                        "✅ <b>Платеж успешно получен!</b>\n\n"
                        "🎉 Ваша подписка активирована.\n"
                        "📱 Теперь вы можете использовать VPN сервис.\n\n"
                        "📖 <b>Как подключиться:</b>\n"
                        "1. Нажмите '<b>📖 Инструкция по подключению</b>' ниже\n"
                        "2. Установите приложение для вашей платформы\n"
                        "3. Получите конфигурацию в '<b>📱 Моя подписка</b>'\n"
                        "4. Импортируйте ссылку в приложение",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="📖 Инструкция по подключению", callback_data="show_connection_guide")],
                            [InlineKeyboardButton(text="📱 Моя подписка", callback_data="my_subscription")],
                            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="show_main_menu")]
                        ])
                    )
                    await callback.answer("✅ Платеж успешно обработан!")
                else:
                    await callback.answer("❌ [USER-006] Ошибка активации подписки",reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")]
                        ]))
            else:
                logger.warning(f"⚠️ Платеж {payment_id} еще не оплачен. Статус: {payment_info.get('status') if payment_info else 'Unknown'}")
                await callback.answer("🔄 Платеж еще не обработан", show_alert=True)
        else:
            logger.warning(f"⚠️ У платежа {payment_id} нет внешнего ID, метод: {payment.payment_method}")
            
            # Для платежей через Stars обрабатываем по-другому
            if payment.payment_method == "telegram_stars":
                logger.info(f"🔄 Проверяем статус платежа Stars: {payment_id}")
                # Здесь может быть дополнительная логика для Stars
                await callback.answer("🔄 Проверка статуса платежа Stars...", show_alert=True)
            # Для платежей через CryptoBot (USDT и TON)
            elif payment.payment_method in ["cryptobot_usdt", "cryptobot_ton"]:
                logger.info(f"🔄 Проверяем статус платежа CryptoBot: {payment_id}")
                await callback.answer("🔄 Проверка статуса платежа CryptoBot...", show_alert=True)
            else:
                logger.error(f"[USER-007] Неизвестный метод оплаты: {payment.payment_method}")
                await callback.answer("❌ [USER-007] Неизвестный метод оплаты", show_alert=True)
                
    except Exception as e:
        logger.error(f"[USER-008] Ошибка при проверке платежа {payment_id}: {format_error_traceback(e)}")
        await callback.answer("❌ [USER-008] Ошибка при проверке платежа", show_alert=True)


async def activate_subscription_after_payment(payment) -> bool:
    """Активация подписки после успешной оплаты"""
    try:
        # Получаем информацию о подписке
        subscription = await subscription_repo.db.get_by_id(Subscription, payment.subscription_id)
        if not subscription:
            logger.error(f"[USER-009] Подписка не найдена: {payment.subscription_id}")
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
            logger.error("[USER-010] Не удалось создать пользователя в marzban")
            return False
        logger.info(f"✅ Подписка активирована: {subscription.id}")
        return True
        
    except Exception as e:
        logger.error(f"[USER-011] Ошибка активации подписки: {format_error_traceback(e)}")
        return False


@user_router.message(F.text == "💳 История платежей")
async def cmd_payment_history(message: Message):
    """
    Обработчик кнопки "История платежей"
    """
    try:
        from src.handlers.payment_stars import cmd_payment_history
        await cmd_payment_history(message)
        
    except Exception as e:
        logger.error(f"[HIST-999] Ошибка в истории платежей: {format_error_traceback(e)}")
        await message.answer(
            "❌ [HIST-999] Произошла ошибка. Попробуйте позже.",
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
                "📱 <b>Ваша подписка</b>\n\n"
                "❌ У вас нет активной подписки.\n\n"
                "💎 <b>Хотите оформить?</b>\n"
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
                        f"📱 <b>Ваша подписка</b>\n\n"
                        f"{status_emoji} <b>Статус:</b> {marzban_user.status}\n"
                        f"📅 <b>Действительна до:</b> {expire_date.strftime('%Y-%m-%d %H:%M')}\n"
                        f"📊 <b>Трафик:</b> {used_gb:.2f}GB / {limit_gb}GB\n"
                        f"🌐 <b>Протокол:</b> {subscription.protocol}\n"
                        f"💰 <b>Тариф:</b> {subscription.plan_name}\n\n"
                    )
                    
                    if marzban_user.subscription_url:
                        text += f"🔗 <b>Подписка:</b> <a href=\"{marzban_user.subscription_url}\">получить конфигурацию</a>"
                else:
                    # Если не удалось получить данные из Marzban
                    expire_date = subscription.expires_at
                    text = (
                        f"📱 <b>Ваша подписка</b>\n\n"
                        f"✅ <b>Статус:</b> Активна\n"
                        f"📅 <b>Действительна до:</b> {expire_date.strftime('%Y-%m-%d %H:%M')}\n"
                        f"🌐 <b>Протокол:</b> {subscription.protocol}\n"
                        f"💰 <b>Тариф:</b> {subscription.plan_name}\n\n"
                        f"⚠️ <i>Конфигурация временно недоступна. Попробуйте позже.</i>"
                    )
            else:
                # Если нет привязки к Marzban
                expire_date = subscription.expires_at
                text = (
                    f"📱 <b>Ваша подписка</b>\n\n"
                    f"✅ <b>Статус:</b> Активна\n"
                    f"📅 <b>Действительна до:</b> {expire_date.strftime('%Y-%m-%d %H:%M')}\n"
                    f"🌐 <b>Протокол:</b> {subscription.protocol}\n"
                    f"💰 <b>Тариф:</b> {subscription.plan_name}\n\n"
                    f"⚠️ <i>Конфигурация готовится...</i>"
                )
        
        keyboard = await get_main_keyboard()
        
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"[SUB-999] Ошибка в моей подписке: {format_error_traceback(e)}")
        await message.answer(
            "❌ [SUB-999] Произошла ошибка при загрузке подписки.",
            parse_mode=ParseMode.HTML
        )


@user_router.callback_query(F.data == "show_connection_guide")
async def show_connection_guide_callback(callback: CallbackQuery):
    """Показать инструкцию по подключению из inline кнопки"""
    try:
        guide_text = (
            "📖 <b>Инструкция по подключению</b>\n\n"
            "Для подключения к VPN вам понадобится специальное приложение-клиент. "
            "Выберите вашу платформу ниже и установите приложение:\n\n"
            "<b>🤖 Android</b>\n"
            "• <a href=\"https://play.google.com/store/apps/details?id=com.happproxy\">Haproxy</a>\n"
            "• <a href=\"https://play.google.com/store/apps/details?id=com.v2raytun.android\">v2RayTun</a>\n"
            "• <a href=\"https://play.google.com/store/apps/details?id=dev.hexasoftware.v2box\">V2Box</a>\n\n"
            "<b>🍎 iOS (iPhone/iPad)</b>\n"
            "• <a href=\"https://apps.apple.com/ru/app/streisand/id6450534064\">Streisand</a>\n"
            "• <a href=\"https://apps.apple.com/app/v2raytun/id6476628951\">v2RayTun</a>\n\n"
            "<b>💻 Windows</b>\n"
            "• <a href=\"https://github.com/hiddify/hiddify-app/releases/download/v2.5.7/Hiddify-Windows-Setup-x64.exe\">Hiddify</a>\n"
            "• <a href=\"https://github.com/2dust/v2rayN/releases\">v2rayN</a>\n"
            "• <a href=\"https://github.com/MatsuriDayo/nekoray/releases\">Nekoray</a>\n\n"
            "<b>🍏 macOS</b>\n"
            "• <a href=\"https://apps.apple.com/us/app/v2box-v2ray-client/id1641370535\">V2Box</a>\n"
            "• <a href=\"https://apps.apple.com/us/app/foxray/id6448898375\">FoXray</a>\n\n"
            "<b>🚀 Как подключиться?</b>\n"
            "1. Перейдите в '<b>📱 Моя подписка</b>'\n"
            "2. Нажмите '<b>🔑 Получить ссылку</b>'\n"
            "3. Скопируйте ссылку\n"
            "4. В приложении-клиенте нажмите '+' или 'Добавить конфигурацию'\n"
            "5. Выберите 'Импорт из буфера обмена'\n\n"
            "<i>💡 Если у вас возникли проблемы, обратитесь в поддержку!</i>"
        )
        
        await message.answer(
            guide_text,
            parse_mode="HTML",
            disable_web_page_preview=True  # Отключаем превью ссылок
        )
        
    except Exception as e:
        logger.error(f"[GUIDE-999] Ошибка в инструкции по подключению: {format_error_traceback(e)}")
        await message.answer(
            "❌ [GUIDE-999] Произошла ошибка при загрузке инструкции.",
            parse_mode="HTML"
        )


@user_router.message(F.text == "�� Статистика")
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
        
        keyboard = await get_main_keyboard()
        
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
        
        keyboard = await get_main_keyboard()
        
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
        
        keyboard = await get_main_keyboard()
        
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
        keyboard = await get_main_keyboard()
        
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
