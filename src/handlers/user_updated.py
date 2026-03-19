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
from src.models import Subscription
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
        [InlineKeyboardButton(text="💳 Криптовалюта (USDT, TON, BTC, ETH...)", callback_data="payment_crypto_pay")],
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


@user_router.callback_query(F.data == "payment_crypto_pay")
async def process_payment_crypto_pay(callback: CallbackQuery):
    """Обработка выбора оплаты через Crypto Pay API (любая криптовалюта)"""
    try:
        logger.info(f"[CRYPTO-001] Starting Crypto Pay payment process for user {callback.from_user.id}")
        
        # Получаем данные о тарифе и протоколе из контекста выбора
        plan = "1_month"  # По умолчанию
        protocol = "vless"  # По умолчанию
        
        from src.core.config import settings
        crypto_prices = settings.subscription_prices  # Базовые цены в USD
        price = crypto_prices[plan]
        
        plan_display_name = {
            "1_month": "1 месяц",
            "3_months": "3 месяца", 
            "6_months": "6 месяцев",
            "1_year": "1 год"
        }.get(plan, plan.replace('_', ' ').title())
        
        logger.info(f"[CRYPTO-002] Payment details: plan={plan}, protocol={protocol}, price=${price}")
        
        # Получаем пользователя
        logger.info(f"[CRYPTO-003] Getting user {callback.from_user.id}")
        user = await user_repo.get_user_by_telegram_id(callback.from_user.id)
        if not user:
            logger.error(f"[CRYPTO-004] User {callback.from_user.id} not found")
            await callback.answer("❌ [CRYPTO-004] Пользователь не найден", show_alert=True)
            return
        
        logger.info(f"[CRYPTO-005] User found: {user.id}")
        
        # Создаем подписку
        logger.info("[CRYPTO-006] Creating subscription")
        subscription = await subscription_repo.create_subscription(
            user_id=user.id,
            plan_name=plan,
            price=price,
            duration_days=get_duration_days(plan),
            status=SubscriptionStatus.PENDING,
            protocol=protocol
        )
        
        if not subscription:
            logger.error("[CRYPTO-007] Failed to create subscription")
            await callback.message.edit_text(
                "❌ [CRYPTO-007] Не удалось создать подписку. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
                ])
            )
            return
        
        logger.info(f"[CRYPTO-008] Subscription created: {subscription.id}")
        
        # Создаем платеж
        logger.info("[CRYPTO-009] Creating payment record")
        payment = await payment_repo.create_payment(
            user_id=user.id,
            payment_id=None,  # Обновится после создания invoice
            subscription_id=subscription.id,
            amount=price,
            payment_method="crypto_pay",
            description=f"VPN Подписка - {plan_display_name}"
        )
        
        if not payment:
            logger.error("[CRYPTO-010] Failed to create payment record")
            await callback.message.edit_text(
                "❌ [CRYPTO-010] Не удалось создать запись о платеже. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
                ])
            )
            return
        
        logger.info(f"[CRYPTO-011] Payment record created: {payment.id}")
        
        # Создаем инвойс через Crypto Pay API
        logger.info("[CRYPTO-012] Creating Crypto Pay invoice")
        from src.services.crypto_pay import get_crypto_pay_service
        
        crypto_service = get_crypto_pay_service()
        if not crypto_service:
            logger.error("[CRYPTO-013] Crypto Pay service not initialized")
            await callback.message.edit_text(
                "❌ [CRYPTO-013] Сервис крипто-оплаты недоступен. Попробуйте другой способ оплаты.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
                ])
            )
            return
        
        payment_info = await crypto_service.create_invoice(
            amount=price,
            description=f"VPN Подписка - {plan_display_name}",
            fiat="USD",
            accepted_assets=settings.crypto_pay_accepted_assets,
            swap_to=settings.crypto_pay_swap_to,
            expires_in=settings.crypto_pay_expires_in,
            payload=str(payment.id)  # ID платежа для привязки
        )
        
        logger.info(f"[CRYPTO-014] Crypto Pay invoice info: {payment_info}")
        
        # Проверяем успешное создание платежа
        if payment_info and payment_info.get('pay_url'):
            logger.info("[CRYPTO-015] Payment invoice created successfully")
            
            # Обновляем платеж с внешним ID
            if payment_info.get('invoice_id'):
                logger.info(f"[CRYPTO-016] Updating payment with invoice_id: {payment_info['invoice_id']}")
                await payment_repo.update_payment_status(
                    payment.id, 
                    "pending",  # Не completed, а pending т.к. Оплата еще не прошла
                    payment_info["invoice_id"]
                )
                logger.info("[CRYPTO-017] Payment updated successfully")
            
            await callback.message.edit_text(
                f"✅ Конфигурация сохранена!\n\n"
                f"📋 <b>Детали заказа:</b>\n"
                f"Тариф: {plan_display_name}\n"
                f"Протокол: {protocol.upper()}\n"
                f"Цена: ${price}\n\n"
                f"💳 <b>Способ оплаты:</b> Криптовалюта\n"
                f"💰 <b>Принимаемые валюты:</b> {settings.crypto_pay_accepted_assets}\n\n"
                f"🔗 <b>Ссылка для оплаты:</b>\n"
                f"<a href=\"{payment_info['pay_url']}\">Оплатить криптовалютой</a>\n\n"
                f"⏰ Оплата будет обработана автоматически после поступления средств",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="� Оплатить", url=payment_info['pay_url'])],
                    [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment_{payment.id}")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
                ]),
                parse_mode="HTML"
            )
            logger.info("[CRYPTO-018] Payment message sent to user")
        else:
            logger.error(f"[CRYPTO-019] Crypto Pay invoice creation failed: {payment_info}")
            await callback.message.edit_text(
                "❌ [CRYPTO-019] Не удалось создать инвойс. Попробуйте другой способ оплаты.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="show_main_menu")]
                ])
            )
    except Exception as e:
        logger.error(f"[CRYPTO-999] Критическая ошибка в крипто-оплате: {format_error_traceback(e)}")
        await callback.message.edit_text(
            "❌ [CRYPTO-999] Произошла критическая ошибка при обработке платежа. Пожалуйста, свяжитесь с поддержкой.",
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
        
        # Если есть внешний ID платежа, проверяем через соответствующий API
        if payment.payment_id:
            payment_info = None
            
            if payment.payment_method == "crypto_pay":
                # Проверяем через Crypto Pay API
                from src.services.crypto_pay import get_crypto_pay_service
                crypto_service = get_crypto_pay_service()
                if crypto_service:
                    payment_info = await crypto_service.get_invoice(payment.payment_id)
                    # Crypto Pay API возвращает объект инвойса напрямую
                    # Статус может быть 'paid', 'active', 'pending', 'expired', 'failed'
                    if payment_info:
                        logger.info(f"  - Crypto Pay API response: {payment_info}")
                        api_status = payment_info.get("status")
                        logger.info(f"  - Crypto Pay status: {api_status}")
                        # Используем статус напрямую из API
                        payment_info = {"status": api_status}
            else:
                # Проверяем через старый CryptoBot API
                payment_info = await payment_processor.check_payment(payment.payment_id)
            
            logger.info(f"  - payment_info from API: {payment_info}")
            
            # Проверяем статус оплаченности
            if payment_info:
                api_status = payment_info.get("status")
                # Crypto Pay API может возвращать "paid" или "active" для оплаченных инвойсов
                if api_status in ["paid", "active"]:
                    logger.info(f"✅ Платеж {payment_id} оплачен (статус: {api_status}), активируем подписку")
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
        
        # Вычисляем дату истечения подписки
        from datetime import datetime, timedelta
        expire_date = datetime.utcnow() + timedelta(days=subscription.duration_days)
        
        # Обновляем подписку с датой истечения
        await subscription_repo.update_subscription_with_expiry(
            subscription.id,
            status=SubscriptionStatus.ACTIVE,
            expires_at=expire_date
        )
        
        # Активируем подписку в Marzban
        user = await user_repo.get_user_by_id(payment.user_id)
        marzban_user = await marzban_service.create_user(
            user=user,
            subscription=subscription
        )

        
        if not marzban_user:
            logger.error("[USER-010] Не удалось создать пользователя в marzban")
            return False
        
        logger.info(f"✅ Подписка активирована: {subscription.id}, expires_at: {expire_date}")
        return True
        
    except Exception as e:
        logger.error(f"[USER-011] Ошибка активации подписки: {format_error_traceback(e)}")
        return False


@user_router.message(F.text == "Инструкция по подключению")
async def cmd_connection_guide(message: Message):
    """
    Обработчик кнопки "Инструкция по подключению"
    """
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
            user = await user_repo.get_user_by_telegram_id(message.from_user.id)
            if user.marzban_username:
                marzban_user = await marzban_service.get_user(user.marzban_username)
                
                if marzban_user is not None:
                    # Формируем информацию о подписке
                    expire_date = datetime.fromtimestamp(marzban_user.expire) if marzban_user.expire else None
                    used_gb = marzban_user.used_traffic / (1024**3)
                    limit_gb = marzban_user.data_limit / (1024**3) if marzban_user.data_limit > 0 else "∞"
                    
                    status_emoji = {
                        "active": "✅",
                        "disabled": "❌",
                        "limited": "⚠️",
                        "expired": "🕐"
                    }.get(marzban_user.status, "❓")
                    
                    expire_date_str = expire_date.strftime('%Y-%m-%d %H:%M') if expire_date else "Неизвестно"
                    
                    text = (
                        f"📱 <b>Ваша подписка</b>\n\n"
                        f"{status_emoji} <b>Статус:</b> {marzban_user.status}\n"
                        f"📅 <b>Действительна до:</b> {expire_date_str}\n"
                        f"📊 <b>Трафик:</b> {used_gb:.2f}GB / {limit_gb}GB\n"
                        f"🌐 <b>Протокол:</b> {subscription.protocol}\n"
                        f"💰 <b>Тариф:</b> {subscription.plan_name}\n\n"
                    )
                    
                    if marzban_user.subscription_url:
                        text += f"🔗 <b>Подписка:</b> <a href=\"{marzban_user.subscription_url}\">получить конфигурацию</a>"
                else:
                    # Если не удалось получить данные из Marzban
                    expire_date = subscription.expires_at
                    expire_date_str = expire_date.strftime('%Y-%m-%d %H:%M') if expire_date else "Неизвестно"
                    text = (
                        f"📱 <b>Ваша подписка</b>\n\n"
                        f"✅ <b>Статус:</b> Активна\n"
                        f"📅 <b>Действительна до:</b> {expire_date_str}\n"
                        f"🌐 <b>Протокол:</b> {subscription.protocol}\n"
                        f"💰 <b>Тариф:</b> {subscription.plan_name}\n\n"
                        f"⚠️ <i>Конфигурация временно недоступна. Попробуйте позже.</i>"
                    )
            else:
                # Если нет привязки к Marzban
                expire_date = subscription.expires_at
                expire_date_str = expire_date.strftime('%Y-%m-%d %H:%M') if expire_date else "Неизвестно"
                text = (
                    f"📱 <b>Ваша подписка</b>\n\n"
                    f"✅ <b>Статус:</b> Активна\n"
                    f"📅 <b>Действительна до:</b> {expire_date_str}\n"
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
    await callback.answer()
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
        
        await callback.message.answer(
            guide_text,
            parse_mode="HTML",
            disable_web_page_preview=True  # Отключаем превью ссылок
        )
        
    except Exception as e:
        logger.error(f"[GUIDE-999] Ошибка в инструкции по подключению: {format_error_traceback(e)}")
        await callback.message.answer(
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


@user_router.message(F.text == "Поддержка")
async def cmd_support(message: Message):
    """
    Обработчик кнопки "Поддержка"
    """
    try:
        text = (
                "💬 <b>Поддержка</b><br><br>"
                "🆘 <b>Нужна помощь?</b><br><br>"
                f"📝 <b>Напишите нам: {settings.support_username}</b><br>"
                "• Опишите вашу проблему<br>"
                f"• Укажите ваш Telegram ID: <code>{str(message.from_user.id)}</code><br>"
              "• Приложите скриншоты если нужно<br><br>"
              "⏰ <b>Время ответа:</b> обычно 5-15 минут<br><br>"
              "💡 <b>Частые вопросы:</b><br>"
              "• Как подключить VPN?<br>"
              "• Не работает конфигурация<br>"
              "• Проблемы с оплатой<br><br>"
              "📧 <i>Мы всегда готовы помочь!</i>"
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
