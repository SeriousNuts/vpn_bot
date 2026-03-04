"""
Клавиатуры для платежных функций
"""

from typing import List, Dict, Any
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


async def get_payment_plans_keyboard(plans: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры с тарифами для оплаты
    
    Args:
        plans: Список тарифов
        
    Returns:
        InlineKeyboardMarkup с кнопками тарифов
    """
    builder = InlineKeyboardBuilder()
    
    for plan in plans:
        # Формируем текст кнопки
        button_text = f"🌟 {plan['plan_name']} - {plan['price_in_stars']} ⭐"
        
        if plan['discount_percent'] > 0:
            button_text += f" (-{plan['discount_percent']}%)"
        
        builder.row(
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"buy_plan_{plan['plan_name']}"
            )
        )
    
    # Добавляем кнопки доп. функций
    builder.row(
        InlineKeyboardButton(
            text="💳 История платежей",
            callback_data="payment_history"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="ℹ️ Информация об оплате",
            callback_data="stars_info"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="back_to_main"
        )
    )
    
    return builder.as_markup()


def get_payment_history_keyboard() -> InlineKeyboardMarkup:
    """
    Создание клавиатуры для истории платежей
    
    Returns:
        InlineKeyboardMarkup с кнопками управления
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🔄 Обновить",
            callback_data="refresh_payment_history"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="back_to_main"
        )
    )
    
    return builder.as_markup()


def get_payment_success_keyboard() -> InlineKeyboardMarkup:
    """
    Создание клавиатуры после успешной оплаты
    
    Returns:
        InlineKeyboardMarkup с кнопками действий
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="📱 Моя подписка",
            callback_data="my_subscription"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="back_to_main"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="💬 Поддержка",
            callback_data="support"
        )
    )
    
    return builder.as_markup()


def get_stars_info_keyboard() -> InlineKeyboardMarkup:
    """
    Создание клавиатуры для информации о звёздах
    
    Returns:
        InlineKeyboardMarkup с кнопками действий
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="💎 Купить подписку",
            callback_data="buy_stars"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="back_to_main"
        )
    )
    
    return builder.as_markup()


async def get_payment_methods_keyboard() -> InlineKeyboardMarkup:
    """
    Создание клавиатуры выбора способа оплаты
    
    Returns:
        InlineKeyboardMarkup с кнопками способов оплаты
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="💎 Telegram Stars",
            callback_data="payment_method_stars"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="💳 Картой (Coming Soon)",
            callback_data="payment_method_card"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="back_to_main"
        )
    )
    
    return builder.as_markup()


def get_payment_confirmation_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры подтверждения платежа
    
    Args:
        payment_id: ID платежа
        
    Returns:
        InlineKeyboardMarkup с кнопками подтверждения
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить оплату",
            callback_data=f"confirm_payment_{payment_id}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="cancel_payment"
        )
    )
    
    return builder.as_markup()


def get_payment_settings_keyboard() -> InlineKeyboardMarkup:
    """
    Создание клавиатуры настроек платежей
    
    Returns:
        InlineKeyboardMarkup с кнопками настроек
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="💳 Способы оплаты",
            callback_data="payment_methods"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="📋 История платежей",
            callback_data="payment_history"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="💎 Информация о звёздах",
            callback_data="stars_info"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="back_to_main"
        )
    )
    
    return builder.as_markup()


def get_refund_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры для возврата платежа
    
    Args:
        payment_id: ID платежа
        
    Returns:
        InlineKeyboardMarkup с кнопками возврата
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="💰 Запросить возврат",
            callback_data=f"refund_payment_{payment_id}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="payment_history"
        )
    )
    
    return builder.as_markup()


def get_payment_support_keyboard() -> InlineKeyboardMarkup:
    """
    Создание клавиатуры поддержки платежей
    
    Returns:
        InlineKeyboardMarkup с кнопками поддержки
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="📝 Написать в поддержку",
            callback_data="contact_support_payment"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="❓ Частые вопросы",
            callback_data="payment_faq"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="payment_settings"
        )
    )
    
    return builder.as_markup()


def get_payment_faq_keyboard() -> InlineKeyboardMarkup:
    """
    Создание клавиатуры FAQ по платежам
    
    Returns:
        InlineKeyboardMarkup с кнопками FAQ
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="💎 Что такое Telegram Stars?",
            callback_data="faq_stars"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="💰 Как пополнить баланс?",
            callback_data="faq_recharge"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🛡️ Безопасность платежей",
            callback_data="faq_security"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="⏰ Возврат средств",
            callback_data="faq_refund"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="payment_support"
        )
    )
    
    return builder.as_markup()


# Reply клавиатуры для обычных сообщений
def get_payment_reply_keyboard() -> ReplyKeyboardMarkup:
    """
    Создание reply клавиатуры для платежных команд
    
    Returns:
        ReplyKeyboardMarkup с кнопками команд
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="💎 Купить подписку"),
                KeyboardButton(text="💳 История платежей")
            ],
            [
                KeyboardButton(text="ℹ️ Информация об оплате"),
                KeyboardButton(text="🏠 Главное меню")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )
    
    return keyboard
