"""
Хендлеры для обработки платежей через Telegram Stars
"""

import logging
from typing import Dict, Any, List

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, PreCheckoutQuery, SuccessfulPayment, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from src.services.payment_stars import stars_payment_service
from src.services.notification import NotificationService
from src.keyboards.payment import get_payment_plans_keyboard, get_payment_history_keyboard

logger = logging.getLogger(__name__)

# Создаем роутер
payment_stars_router = Router()

async def process_stars_payment(callback: CallbackQuery, payment, plan_display_name: str, protocol: str, price: float):
    """Обработка платежа через Telegram Stars"""
    try:
        # Создаем invoice для оплаты через Stars
        invoice_link = await stars_payment_service.create_payment_invoice(
            payment_id=payment.id,
            amount=price,
            description=f"VPN Подписка - {plan_display_name}",
            user_id=callback.from_user.id
        )
        
        if invoice_link:
            await callback.message.edit_text(
                f"✅ Конфигурация сохранена!\n\n"
                f"📋 **Детали заказа:**\n"
                f"Тариф: {plan_display_name}\n"
                f"Протокол: {protocol.upper()}\n"
                f"Цена: {price} ⭐\n\n"
                f"💳 **Детали оплаты:**\n"
                f"ID платежа: #{payment.id}\n"
                f"Способ оплаты: Telegram Stars\n\n"
                f"🔗 **Нажмите для оплаты:**\n"
                f"[Оплатить Stars]({invoice_link})\n\n"
                f"⏰ Оплата будет обработана автоматически",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⭐ Оплатить", url=invoice_link)],
                    [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_stars_payment_{payment.id}")]
                ]),
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(
                "❌ Не удалось создать счет для оплаты через Stars. Попробуйте другой способ."
            )
            
    except Exception as e:
        logger.error(f"❌ Ошибка создания платежа через Stars: {format_error_traceback(e)}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при создании платежа. Попробуйте позже."
        )


@payment_stars_router.callback_query(F.data.startswith("check_stars_payment_"))
async def check_stars_payment_status(callback: CallbackQuery):
    """Проверка статуса оплаты через Stars"""
    try:
        payment_id = int(callback.data.replace("check_stars_payment_", ""))
        
        # Здесь должна быть логика проверки статуса платежа
        # В реальном приложении нужно проверять через Telegram Bot API
        
        await callback.answer("🔄 Проверка статуса оплаты...")
        
        # Временно показываем сообщение о проверке
        await callback.message.edit_text(
            "🔄 Проверка статуса оплаты...\n\n"
            "Пожалуйста, подождите несколько секунд.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Проверить еще раз", callback_data=f"check_stars_payment_{payment_id}")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
            ])
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки оплаты Stars: {format_error_traceback(e)}")
        await callback.answer("❌ Произошла ошибка при проверке оплаты", show_alert=True)

@payment_stars_router.message(Command("buy_stars"))
async def cmd_buy_stars(message: Message):
    """
    Обработчик команды /buy_stars - покупка подписки за звёзды
    """
    try:
        # Получаем доступные тарифы
        plans = await stars_payment_service.get_payment_plans()
        
        if not plans:
            await message.answer(
                "❌ К сожалению, в данный момент нет доступных тарифов для оплаты звёздами.\n"
                "Попробуйте позже или свяжитесь с поддержкой.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Формируем сообщение с тарифами
        text = "💎 **Оплата VPN подписки звёздами Telegram**\n\n"
        text += "Выберите подходящий тариф:\n\n"
        
        for plan in plans:
            text += f"🌟 <b>{plan['plan_name']}</b>\n"
            text += f"   💰 Цена: {plan['price_in_stars']} звёзд\n"
            text += f"   ⏰ Длительность: {plan['duration_days']} дней\n"
            text += f"   📅 Эквивалент в месяц: {plan['monthly_equivalent']} звёзд\n"
            
            if plan['discount_percent'] > 0:
                text += f"   🎉 Экономия: {plan['discount_percent']}%\n"
            
            text += "\n"
        
        text += "💡 <i>Оплата через Telegram Stars - безопасно и быстро!</i>"
        
        # Создаем клавиатуру с тарифами
        keyboard = await get_payment_plans_keyboard(plans)
        
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /buy_stars: {format_error_traceback(e)}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


@payment_stars_router.callback_query(F.data.startswith("buy_plan_"))
async def callback_buy_plan(callback: CallbackQuery):
    """
    Обработчик выбора тарифа для покупки
    """
    try:
        # Извлекаем название тарифа
        plan_name = callback.data.replace("buy_plan_", "")
        
        # Создаем инвойс
        invoice_data = await stars_payment_service.create_stars_invoice(
            user_id=callback.from_user.id,
            plan_name=plan_name
        )
        
        if not invoice_data:
            await callback.answer(
                "❌ Не удалось создать платеж. Попробуйте позже. Нет инвойса",
                show_alert=True
            )
            return
        
        # Отправляем инвойс
        await callback.bot.send_invoice(
            chat_id=callback.from_user.id,
            **invoice_data["invoice_data"]
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка в callback buy_plan: {format_error_traceback(e)}")
        await callback.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            show_alert=True
        )


@payment_stars_router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """
    Обработка pre-checkout запроса
    """
    try:
        # Проверяем платеж
        is_valid = await stars_payment_service.process_pre_checkout_query(pre_checkout_query)
        
        if is_valid:
            await pre_checkout_query.answer(ok=True)
        else:
            await pre_checkout_query.answer(
                ok=False,
                error_message="❌ Проверка платежа не пройдена. Попробуйте снова."
            )
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки pre-checkout: {format_error_traceback(e)}")
        await pre_checkout_query.answer(
            ok=False,
            error_message="❌ Произошла ошибка. Попробуйте позже."
        )


@payment_stars_router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    """
    Обработка успешного платежа
    """
    try:
        successful_payment = message.successful_payment
        
        # Обрабатываем платеж
        success = await stars_payment_service.process_successful_payment(successful_payment)
        
        if success:
            # Формируем успешное сообщение
            text = "🎉 **Платеж успешно выполнен!**\n\n"
            text += "✅ Ваша VPN подписка активирована.\n"
            text += "📱 Конфигурация будет отправлена вам в ближайшее время.\n\n"
            text += "💡 <i>Спасибо за покупку! Приятного использования!</i>"
            
            await message.answer(
                text,
                parse_mode=ParseMode.HTML
            )
        else:
            await message.answer(
                "❌ Произошла ошибка при активации подписки.\n"
                "Пожалуйста, свяжитесь с поддержкой.",
                parse_mode=ParseMode.HTML
            )
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки успешного платежа: {format_error_traceback(e)}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, свяжитесь с поддержкой.",
            parse_mode=ParseMode.HTML
        )


@payment_stars_router.message(Command("payment_history"))
async def cmd_payment_history(message: Message):
    """
    Обработчик команды /payment_history - история платежей
    """
    try:
        # Получаем историю платежей
        payments = await stars_payment_service.get_user_payment_history(
            user_id=message.from_user.id,
            limit=10
        )
        
        if not payments:
            await message.answer(
                "📭 **История платежей пуста**\n\n"
                "У вас еще не было платежей через Telegram Stars.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Формируем сообщение с историей
        text = "📋 **История ваших платежей**\n\n"
        
        for payment in payments:
            status_emoji = {
                "pending": "⏳",
                "completed": "✅",
                "failed": "❌",
                "refunded": "💰"
            }.get(payment["status"], "❓")
            
            text += f"{status_emoji} **{payment['plan_name']}**\n"
            text += f"   💰 Сумма: {payment['amount']} {payment['currency']}\n"
            text += f"   ⏰ Длительность: {payment['duration_days']} дней\n"
            text += f"   📅 Дата: {payment['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
            
            if payment["completed_at"]:
                text += f"   ✅ Оплачен: {payment['completed_at'].strftime('%Y-%m-%d %H:%M')}\n"
            
            text += "\n"
        
        # Создаем клавиатуру
        keyboard = get_payment_history_keyboard()
        
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /payment_history: {format_error_traceback(e)}")
        await message.answer(
            "❌ Произошла ошибка при загрузке истории платежей.",
            parse_mode=ParseMode.HTML
        )


@payment_stars_router.callback_query(F.data == "refresh_payment_history")
async def callback_refresh_payment_history(callback: CallbackQuery):
    """
    Обновление истории платежей
    """
    try:
        # Получаем обновленную историю
        payments = await stars_payment_service.get_user_payment_history(
            user_id=callback.from_user.id,
            limit=10
        )
        
        if not payments:
            text = "📭 **История платежей пуста**\n\n"
            text += "У вас еще не было платежей через Telegram Stars."
        else:
            text = "📋 **История ваших платежей (обновлено)**\n\n"
            
            for payment in payments:
                status_emoji = {
                    "pending": "⏳",
                    "completed": "✅",
                    "failed": "❌",
                    "refunded": "💰"
                }.get(payment["status"], "❓")
                
                text += f"{status_emoji} **{payment['plan_name']}**\n"
                text += f"   💰 Сумма: {payment['amount']} {payment['currency']}\n"
                text += f"   ⏰ Длительность: {payment['duration_days']} дней\n"
                text += f"   📅 Дата: {payment['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
                
                if payment["completed_at"]:
                    text += f"   ✅ Оплачен: {payment['completed_at'].strftime('%Y-%m-%d %H:%M')}\n"
                
                text += "\n"
        
        # Обновляем сообщение
        await callback.message.edit_text(
            text,
            reply_markup=get_payment_history_keyboard(),
            parse_mode=ParseMode.HTML
        )
        
        await callback.answer("🔄 История платежей обновлена")
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления истории платежей: {format_error_traceback(e)}")
        await callback.answer(
            "❌ Произошла ошибка при обновлении.",
            show_alert=True
        )


@payment_stars_router.callback_query(F.data == "back_to_main")
async def callback_back_to_main(callback: CallbackQuery):
    """
    Возврат в главное меню
    """
    try:
        from src.handlers.user_updated import get_back_to_main_inline_keyboard
        
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
        await callback.answer(
            "❌ Произошла ошибка.",
            show_alert=True
        )


@payment_stars_router.message(Command("stars_info"))
async def cmd_stars_info(message: Message):
    """
    Обработчик команды /stars_info - информация о платежах звёздами
    """
    try:
        text = "💎 **Оплата через Telegram Stars**\n\n"
        text += "🌟 **Что такое Telegram Stars?**\n"
        text += "Это внутренняя валюта Telegram, которую можно использовать для оплаты услуг.\n\n"
        
        text += "💰 **Как пополнить баланс звёзд?**\n"
        text += "1. Откройте Telegram\n"
        text += "2. Перейдите в Настройки → Telegram Stars\n"
        text += "3. Нажмите 'Пополнить баланс'\n"
        text += "4. Выберите удобный способ оплаты\n\n"
        
        text += "🛡️ **Преимущества оплаты звёздами:**\n"
        text += "✅ Безопасность - платежи внутри Telegram\n"
        text += "✅ Скорость - мгновенное зачисление\n"
        text += "✅ Удобство - не нужно вводить данные карт\n"
        text += "✅ Скидки - выгодные тарифы за длительные подписки\n\n"
        
        text += "📋 **Доступные тарифы:**\n"
        
        plans = await stars_payment_service.get_payment_plans()
        for plan in plans:
            text += f"• {plan['plan_name']}: {plan['price_in_stars']} звёзд"
            if plan['discount_percent'] > 0:
                text += f" (экономия {plan['discount_percent']}%)"
            text += "\n"
        
        text += "\n💡 <i>Для покупки используйте команду /buy_stars</i>"
        
        await message.answer(
            text,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /stars_info: {format_error_traceback(e)}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            parse_mode=ParseMode.HTML
        )
