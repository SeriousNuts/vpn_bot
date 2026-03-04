"""
Сервис для обработки платежей через Telegram Stars API
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from aiogram.types import PreCheckoutQuery, SuccessfulPayment, LabeledPrice
from aiogram.enums import Currency

from src.core.config import settings
from src.core.database import payment_repo, subscription_repo, user_repo
from src.models import Payment, User, Subscription
from src.enums import PaymentStatus, SubscriptionStatus
from src.services.notification import NotificationService

logger = logging.getLogger(__name__)


class TelegramStarsPaymentService:
    """
    Сервис для обработки платежей через Telegram Stars
    """
    
    def __init__(self):
        self.notification_service = NotificationService()
        
        # Цены в звёздах для разных тарифов
        self.plans_prices = {
            "1_month": 50,    # 50 звёзд за 1 месяц
            "3_months": 135,   # 135 звёзд за 3 месяца (10% скидка)
            "6_months": 250,   # 250 звёзд за 6 месяцев (17% скидка)
            "1_year": 450,     # 450 звёзд за 1 год (25% скидка)
        }
        
        # Длительность подписок в днях
        self.plans_duration = {
            "1_month": 30,
            "3_months": 90,
            "6_months": 180,
            "1_year": 365,
        }
    
    async def create_stars_invoice(
        self, 
        user_id: int, 
        plan_name: str, 
        description: str = None
    ) -> Dict[str, Any]:
        """
        Создание инвойса для оплаты звёздами
        
        Args:
            user_id: Telegram ID пользователя
            plan_name: Название тарифа
            description: Описание платежа
            
        Returns:
            Dict с параметрами для отправки инвойса
        """
        try:
            # Проверяем существование тарифа
            if plan_name not in self.plans_prices:
                logging.error(f"❌ Неизвестный тариф: {plan_name}")
                return None
            
            price_in_stars = self.plans_prices[plan_name]
            duration_days = self.plans_duration[plan_name]
            
            # Создаем запись о платеже в базе данных
            payment = await payment_repo.create_payment(
                user_id=user_id,
                amount=price_in_stars,
                currency="XTR",  # Telegram Stars
                payment_method="telegram_stars",
                plan_name=plan_name,
                status=PaymentStatus.PENDING,
                duration_days=duration_days
            )
            
            if not payment:
                logger.error(f"❌ Не удалось создать запись о платеже для пользователя {user_id}")
                return None
            
            # Формируем описание
            if not description:
                description = f"VPN подписка на {duration_days} дней"
            
            # Создаем цены для инвойса
            prices = [
                LabeledPrice(
                    label=f"VPN подписка {plan_name}",
                    amount=price_in_stars * 100  # Telegram использует копейки/центы
                )
            ]
            
            invoice_data = {
                "title": "VPN подписка",
                "description": description,
                "payload": str(payment.id),  # ID платежа как payload
                "provider_token": "",  # Пусто для Telegram Stars
                "currency": Currency.XTR,  # Telegram Stars
                "prices": prices,
                "need_name": False,
                "need_phone_number": False,
                "need_email": False,
                "need_shipping_address": False,
                "send_phone_number_to_provider": False,
                "send_email_to_provider": False,
                "is_flexible": False,
            }
            
            logger.info(f"✅ Создан инвойс для оплаты звёздами: пользователь {user_id}, тариф {plan_name}, {price_in_stars} звёзд")
            
            return {
                "invoice_data": invoice_data,
                "payment_id": payment.id,
                "price_in_stars": price_in_stars,
                "duration_days": duration_days
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания инвойса для звёзд: {e}")
            return None
    
    async def process_pre_checkout_query(self, pre_checkout_query: PreCheckoutQuery) -> bool:
        """
        Обработка pre-checkout запроса
        
        Args:
            pre_checkout_query: PreCheckoutQuery от Telegram
            
        Returns:
            True если проверка пройдена, иначе False
        """
        try:
            # Получаем ID платежа из payload
            payment_id = int(pre_checkout_query.invoice_payload)
            
            # Проверяем существование платежа
            payment = await payment_repo.payment_repo.get_payment(payment_id)
            if not payment:
                logger.error(f"❌ Платеж не найден: {payment_id}")
                return False
            
            # Проверяем статус платежа
            if payment.status != PaymentStatus.PENDING:
                logger.error(f"❌ Платеж уже обработан: {payment_id}, статус: {payment.status}")
                return False
            
            # Проверяем пользователя
            user = await user_repo.get_user(payment.user_id)
            if not user:
                logger.error(f"❌ Пользователь не найден: {payment.user_id}")
                return False
            
            # Проверяем сумму
            expected_amount = self.plans_prices.get(payment.plan_name, 0)
            actual_amount = pre_checkout_query.total_amount // 100  # Конвертируем из копеек
            
            if actual_amount != expected_amount:
                logger.error(f"❌ Несоответствие суммы: ожидается {expected_amount}, получено {actual_amount}")
                return False
            
            logger.info(f"✅ Pre-checkout пройден для платежа {payment_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки pre-checkout: {e}")
            return False
    
    async def process_successful_payment(self, successful_payment: SuccessfulPayment) -> bool:
        """
        Обработка успешного платежа
        
        Args:
            successful_payment: SuccessfulPayment от Telegram
            
        Returns:
            True если платеж успешно обработан, иначе False
        """
        try:
            # Получаем ID платежа из payload
            payment_id = int(successful_payment.invoice_payload)
            
            # Получаем информацию о платеже
            payment = await payment_repo.payment_repo.get_payment(payment_id)
            if not payment:
                logger.error(f"❌ Платеж не найден: {payment_id}")
                return False
            
            # Проверяем текущий статус
            if payment.status != PaymentStatus.PENDING:
                logger.warning(f"⚠️ Платеж уже обработан: {payment_id}, статус: {payment.status}")
                return True
            
            # Обновляем статус платежа
            await payment_repo.update_payment_status(
                payment.id,
                PaymentStatus.COMPLETED
            )
            
            # Активируем подписку
            success = await self._activate_subscription(payment)
            
            if success:
                logger.info(f"✅ Платеж успешно обработан: {payment_id}, пользователь {payment.user_id}")
                
                # Отправляем уведомление
                await self.notification_service.send_payment_confirmation(
                    payment.user_id, 
                    payment.plan_name,
                    payment.duration_days
                )
                
                return True
            else:
                logger.error(f"❌ Не удалось активировать подписку для платежа {payment_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки успешного платежа: {e}")
            return False
    
    async def _activate_subscription(self, payment: Payment) -> bool:
        """
        Активация подписки после успешной оплаты
        
        Args:
            payment: Объект платежа
            
        Returns:
            True если подписка активирована, иначе False
        """
        try:
            # Получаем пользователя
            user = await user_repo.get_user(payment.user_id)
            if not user:
                logger.error(f"❌ Пользователь не найден: {payment.user_id}")
                return False
            
            # Создаем подписку
            subscription = await subscription_repo.create_subscription(
                user_id=payment.user_id,
                plan_name=payment.plan_name,
                price=payment.amount,
                duration_days=payment.duration_days,
                protocol="vless",  # Протокол по умолчанию
                status=SubscriptionStatus.ACTIVE
            )
            
            if not subscription:
                logger.error(f"❌ Не удалось создать подписку для пользователя {payment.user_id}")
                return False
            
            # Обновляем баланс пользователя
            user.balance = max(0, user.balance - payment.amount)
            await user_repo.update_user(user)
            
            logger.info(f"✅ Подписка активирована: пользователь {payment.user_id}, тариф {payment.plan_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка активации подписки: {e}")
            return False
    
    async def get_payment_plans(self) -> List[Dict[str, Any]]:
        """
        Получение списка доступных тарифов
        
        Returns:
            List с информацией о тарифах
        """
        plans = []
        
        for plan_name, price_in_stars in self.plans_prices.items():
            duration_days = self.plans_duration[plan_name]
            
            # Рассчитываем экономию
            base_price = 50  # Базовая цена за месяц
            monthly_equivalent = price_in_stars / (duration_days / 30)
            discount_percent = round((1 - monthly_equivalent / base_price) * 100)
            
            plans.append({
                "plan_name": plan_name,
                "price_in_stars": price_in_stars,
                "duration_days": duration_days,
                "monthly_equivalent": round(monthly_equivalent, 1),
                "discount_percent": discount_percent,
                "description": self._get_plan_description(plan_name, duration_days, discount_percent)
            })
        
        return sorted(plans, key=lambda x: x["duration_days"])
    
    def _get_plan_description(self, plan_name: str, duration_days: int, discount_percent: int) -> str:
        """
        Генерация описания тарифа
        
        Args:
            plan_name: Название тарифа
            duration_days: Длительность в днях
            discount_percent: Процент скидки
            
        Returns:
            Строка с описанием
        """
        base_descriptions = {
            "1_month": "1 месяц VPN подписки",
            "3_months": "3 месяца VPN подписки",
            "6_months": "6 месяцев VPN подписки",
            "1_year": "1 год VPN подписки"
        }
        
        description = base_descriptions.get(plan_name, f"{duration_days} дней VPN подписки")
        
        if discount_percent > 0:
            description += f" (экономия {discount_percent}%)"
        
        return description
    
    async def get_user_payment_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получение истории платежей пользователя
        
        Args:
            user_id: Telegram ID пользователя
            limit: Лимит записей
            
        Returns:
            List с информацией о платежах
        """
        try:
            payments = await payment_repo.get_user_payments(user_id, limit=limit)
            
            result = []
            for payment in payments:
                result.append({
                    "id": payment.id,
                    "plan_name": payment.plan_name,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "status": payment.status,
                    "created_at": payment.created_at,
                    "completed_at": payment.completed_at,
                    "duration_days": payment.duration_days
                })
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения истории платежей: {e}")
            return []
    
    async def refund_payment(self, payment_id: int, reason: str = None) -> bool:
        """
        Возврат платежа (если поддерживается)
        
        Args:
            payment_id: ID платежа
            reason: Причина возврата
            
        Returns:
            True если возврат выполнен, иначе False
        """
        try:
            payment = await payment_repo.payment_repo.get_payment(payment_id)
            if not payment:
                logger.error(f"❌ Платеж не найден: {payment_id}")
                return False
            
            if payment.status != PaymentStatus.COMPLETED:
                logger.error(f"❌ Нельзя вернуть платеж со статусом: {payment.status}")
                return False
            
            # Telegram Stars API не поддерживает возвраты
            # Но можно деактивировать подписку и вернуть баланс
            logger.warning(f"⚠️ Возврат платежа {payment_id} не поддерживается Telegram Stars API")
            
            # Здесь можно добавить логику деактивации подписки
            # и возврата внутренних средств пользователя
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка возврата платежа: {e}")
            return False


# Глобальный экземпляр сервиса
stars_payment_service = TelegramStarsPaymentService()
