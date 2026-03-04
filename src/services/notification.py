"""
Сервис уведомлений для VPN Bot
"""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import selectinload

from src.core.database import subscription_repo, notification_repo
from src.models import Subscription
from src.services.marzban import marzban_service
from utils.format_error import format_error_traceback

logger = logging.getLogger(__name__)

class NotificationService:
    """Сервис для управления уведомлениями и запланированными задачами"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()
    
    def _setup_jobs(self):
        """Настройка запланированных задач"""
        # Проверка истекающих подписок каждые 6 часов
        self.scheduler.add_job(
            self.check_expiring_subscriptions,
            IntervalTrigger(hours=6),
            id='check_expiring',
            name='Check expiring subscriptions',
            replace_existing=True
        )
        
        # Проверка истекших подписок каждый час
        self.scheduler.add_job(
            self.check_expired_subscriptions,
            IntervalTrigger(hours=1),
            id='check_expired',
            name='Check expired subscriptions',
            replace_existing=True
        )
    
    async def start(self):
        """Запуск сервиса уведомлений"""
        try:
            self.scheduler.start()
            logger.info("Сервис уведомлений запущен")
        except Exception as e:
            logger.error(f"Не удалось запустить сервис уведомлений: {format_error_traceback(e)}")
            raise
    
    async def stop(self):
        """Остановка сервиса уведомлений"""
        try:
            self.scheduler.shutdown()
            logger.info("Сервис уведомлений остановлен")
        except Exception as e:
            logger.error(f"Не удалось остановить сервис уведомлений: {format_error_traceback(e)}")
    
    async def send_payment_confirmation(self, user_id: int, subscription: Subscription):
        """Отправить подтверждение платежа"""
        try:
            from src.bot import get_bot
            bot = get_bot()
            
            text = (
                f"✅ **Платеж подтвержден!**\n\n"
                f"🎉 Ваша VPN подписка теперь активна!\n\n"
                f"📦 Тариф: {subscription.plan_name.replace('_', ' ').title()}\n"
                f"⏱️ Длительность: {subscription.duration_days} дней\n"
                f"🔗 Протокол: {subscription.protocol.upper()}\n\n"
                f"Используйте '📱 Моя подписка' для просмотра вашей конфигурации."
            )
            
            await bot.send_message(user_id, text)
            
            # Логирование уведомления
            await notification_repo.create_notification(
                user_id=user_id,
                notification_type="payment_confirmed",
                message="Подтверждение платежа отправлено",
                success=True
            )
            
        except Exception as e:
            logger.error(f"Не удалось отправить подтверждение платежа пользователю {user_id}: {format_error_traceback(e)}")
            # Логирование неудачного уведомления
            await notification_repo.create_notification(
                user_id=user_id,
                notification_type="payment_confirmed",
                message="Не удалось отправить подтверждение платежа",
                success=False,
                error_message=str(e)
            )
    
    async def send_welcome_message(self, user_id: int, first_name: str):
        """Отправить приветственное сообщение"""
        try:
            from src.bot import get_bot
            bot = get_bot()
            
            text = (
                f"🎉 Добро пожаловать в VPN Bot, {first_name}!\n\n"
                f"Вот как начать:\n"
                f"1. 💰 Выберите тарифный план\n"
                f"2. 💳 Завершите оплату\n"
                f"3. 📱 Получите вашу VPN конфигурацию\n"
                f"4. 🔗 Подключитесь и наслаждайтесь безопасным серфингом!\n\n"
                f"Нужна помощь? Используйте кнопку 🆘 Поддержка."
            )
            
            await bot.send_message(user_id, text)
            
            # Логирование уведомления
            await notification_repo.create_notification(
                user_id=user_id,
                notification_type="welcome",
                message="Приветственное сообщение отправлено",
                success=True
            )
            
        except Exception as e:
            logger.error(f"Не удалось отправить приветственное сообщение пользователю {user_id}: {format_error_traceback(e)}")
            # Логирование неудачного уведомления
            await notification_repo.create_notification(
                user_id=user_id,
                notification_type="welcome",
                message="Не удалось отправить приветственное сообщение",
                success=False,
                error_message=str(e)
            )
    
    async def send_expiry_notification(self, user_id: int, subscription: Subscription, days_remaining: int):
        """Отправить уведомление об истечении подписки"""
        try:
            from src.bot import get_bot
            bot = get_bot()
            
            if days_remaining <= 1:
                urgency = "⚠️ **СРОЧНО**"
                message = "Ваша подписка истекает СЕГОДНЯ!"
            elif days_remaining <= 3:
                urgency = "⏰ **НАПОМИНАНИЕ**"
                message = f"Ваша подписка истекает через {days_remaining} дней!"
            else:
                urgency = "📅 **УВЕДОМЛЕНИЕ**"
                message = f"Ваша подписка истекает через {days_remaining} дней."
            
            text = (
                f"{urgency}\n\n"
                f"{message}\n\n"
                f"📦 Тариф: {subscription.plan_name.replace('_', ' ').title()}\n"
                f"🔗 Протокол: {subscription.protocol.upper()}\n\n"
                f"Нажмите '💰 Купить подписку' для продления вашего плана."
            )
            
            await bot.send_message(user_id, text)
            
            # Логирование уведомления
            await notification_repo.create_notification(
                user_id=user_id,
                notification_type="expiry_warning",
                message=f"Уведомление об истечении отправлено ({days_remaining} дней)",
                success=True
            )
            
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление об истечении пользователю {user_id}: {format_error_traceback(e)}")
            # Логирование неудачного уведомления
            await notification_repo.create_notification(
                user_id=user_id,
                notification_type="expiry_warning",
                message=f"Не удалось отправить уведомление об истечении ({days_remaining} дней)",
                success=False,
                error_message=str(e)
            )
    
    async def check_expiring_subscriptions(self):
        """Проверить истекающие подписки"""
        try:
            # Получить уведомления о днях из настроек
            notification_days = [3, 1]  # Значения по умолчанию
            
            # Проверить каждый период уведомления
            for days in notification_days:
                expiring_subs = await subscription_repo.get_expiring_subscriptions(days)
                
                for subscription in expiring_subs:
                    await self.send_expiry_notification(
                        subscription.user_id,
                        subscription,
                        days
                    )
                    
                    logger.info(f"Отправлено уведомление об истечении для пользователя {subscription.user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка проверки истекающих подписок: {format_error_traceback(e)}")
    
    async def check_expired_subscriptions(self):
        """Проверить истекшие подписки"""
        try:
            # Получить истекшие подписки
            async with subscription_repo.db.get_session() as session:
                from sqlalchemy import select, and_
                from src.models import Subscription
                from src.enums import SubscriptionStatus
                
                result = await session.execute(
                    select(Subscription)
                    .options(selectinload(Subscription.user))
                    .where(and_(
                        Subscription.status == SubscriptionStatus.ACTIVE,
                        Subscription.expires_at <= datetime.now()
                    ))
                )
                expired_subs = result.scalars().all()
                
                for subscription in expired_subs:
                    await self.deactivate_subscription(subscription)
                    logger.info(f"Деактивирована истекшая подписка для пользователя {subscription.user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка проверки истекших подписок: {format_error_traceback(e)}")
    
    async def deactivate_subscription(self, subscription: Subscription):
        """Деактивировать истекшую подписку"""
        try:
            # Обновить статус подписки
            await subscription_repo.update_subscription_status(
                subscription.id,
                "expired"
            )
            
            # Деактивировать в Marzban если имя пользователя существует
            if subscription.user:
                try:
                    await marzban_service.change_user_status(username=subscription.user.username, status="Disabled")
                except Exception as e:
                    logger.warning(f"Не удалось деактивировать пользователя Marzban {subscription.marzban_username}: {format_error_traceback(e)}")
            
            # Отправить уведомление пользователю
            from src.bot import get_bot
            bot = get_bot()
            
            text = (
                f"⏰ **Подписка истекла**\n\n"
                f"Ваша VPN подписка истекла.\n\n"
                f"📦 Тариф: {subscription.plan_name.replace('_', ' ').title()}\n\n"
                f"Нажмите '💰 Купить подписку' для продления и продолжения использования нашего сервиса."
            )
            
            await bot.send_message(subscription.user_id, text)
            
            # Логирование уведомления
            await notification_repo.create_notification(
                user_id=subscription.user_id,
                notification_type="subscription_expired",
                message="Уведомление об истечении подписки отправлено",
                success=True
            )
            
        except Exception as e:
            logger.error(f"Ошибка деактивации подписки {subscription.id}: {format_error_traceback(e)}")
            # Логирование неудачного уведомления
            await notification_repo.create_notification(
                user_id=subscription.user_id,
                notification_type="subscription_expired",
                message="Не удалось обработать истечение подписки",
                success=False,
                error_message=str(e)
            )

# Глобальный экземпляр сервиса уведомлений
notification_service = NotificationService()
