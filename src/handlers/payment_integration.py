"""
Интеграция платежных хендлеров в основной роутер
"""

from aiogram import Router

from src.handlers.payment_stars import payment_stars_router


def setup_payment_handlers(main_router: Router):
    """
    Настройка платежных хендлеров
    
    Args:
        main_router: Основной роутер бота
    """
    # Включаем роутер платежей через звёзды
    main_router.include_router(payment_stars_router)


async def update_main_keyboard_with_payments():
    """
    Обновление главного меню с кнопками платежей

        
    Returns:
        Обновленная клавиатура главного меню
    """
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📱 Моя подписка"),
                KeyboardButton(text="💎 Купить подписку")
            ],
            [
                KeyboardButton(text="💳 История платежей"),
                KeyboardButton(text="📊 Статистика")
            ],
            [
                KeyboardButton(text="💬 Поддержка"),
                KeyboardButton(text="⚙️ Настройки")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )
    
    return keyboard


# Экспортируем функции для использования в других модулях
__all__ = [
    'setup_payment_handlers',
    'update_main_keyboard_with_payments'
]
