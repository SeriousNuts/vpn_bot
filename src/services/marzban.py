"""
Современный сервис для работы с Marzban API
Основан на официальной библиотеке marzban и документации
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from httpx import HTTPStatusError
from marzban import (
    MarzbanAPI,
    UserCreate,
    UserModify,
    ProxySettings,
    MarzbanTokenCache,
    HTTPValidationError, SystemStats, UserResponse, UsersResponse, SubscriptionUserResponse
)

from src.core.config import settings
from src.enums import ProtocolType
from src.models import User, Subscription
from utils.format_error import format_error_traceback

logger = logging.getLogger(__name__)


class MarzbanService:
    """
    Сервис для управления пользователями Marzban
    Использует официальную библиотеку marzban
    """
    
    def __init__(self):
        self.base_url = settings.marzban_url.rstrip('/')
        self.username = settings.marzban_username
        self.password = settings.marzban_password
        self.api: Optional[MarzbanAPI] = None
        self.token_cache: Optional[MarzbanTokenCache] = None
    
    async def initialize(self) -> bool:
        """Инициализация API и кэша токенов"""
        try:
            # Создаем API клиент
            self.api = MarzbanAPI(base_url=self.base_url)
            
            # Настраиваем кэш токенов с автоматическим обновлением
            self.token_cache = MarzbanTokenCache(
                client=self.api,
                username=self.username,
                password=self.password,
                token_expire_minutes=1440  # 24 часа
            )
            
            # Проверяем подключение
            token = await self.token_cache.get_token()
            if token:
                logger.info("✅ Успешное подключение к Marzban API")
                return True
            else:
                logger.error("❌ Не удалось получить токен Marzban")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Marzban API: {format_error_traceback(e)}")
            return False
    
    async def close(self) -> None:
        """Закрытие API клиента"""
        if self.api:
            await self.api.close()
            logger.info("🔌 Marzban API клиент закрыт")
    
    async def get_token(self) -> Optional[str]:
        """Получение токена из кэша"""
        if not self.token_cache:
            if not await self.initialize():
                return None
        return await self.token_cache.get_token()
    
    async def create_user(self, user: User, subscription: Subscription) -> UserResponse | None:
        """
        Создание нового пользователя в Marzban
        
        Args:
            user: Пользователь из базы данных
            subscription: Подписка пользователя
            
        Returns:
            Dict с данными созданного пользователя или None
        """
        if self.api is None or self.api.client.is_closed:
            await self.initialize()

        token = await self.get_token()
        if not token:
            logger.error("❌ Не удалось получить токен для создания пользователя")
            return None
        
        try:
            # Генерируем имя пользователя на основе Telegram ID
            username = f"tg_{user.telegram_id}"
            
            # Создаем конфигурацию прокси в зависимости от протокола
            proxy_config = self._get_proxy_config(subscription.protocol)
            
            # Рассчитываем время истечения подписки
            expire_timestamp = int((datetime.now() + timedelta(days=subscription.duration_days)).timestamp())
            
            # Создаем пользователя с использованием современных моделей
            new_user = UserCreate(
                username=username,
                proxies={subscription.protocol: proxy_config},
                expire=expire_timestamp,
                data_limit=0,  # Безлимитный трафик
                data_limit_reset_strategy="no_reset"
            )
            
            # Добавляем пользователя в Marzban
            created_user = await self.api.add_user(user=new_user, token=token)
            
            logger.info(f"✅ Пользователь {username} успешно создан в Marzban")
            return created_user
            
        except HTTPStatusError as e:
            if e.response.status_code == 400:
                logger.error(f"❌ Ошибка валидации при создании пользователя: {e.response.text}")
            elif e.response.status_code == 409:
                logger.error(f"❌ Пользователь уже существует: {username}")
            else:
                logger.error(f"❌ Ошибка HTTP при создании пользователя: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка создания пользователя в Marzban: {format_error_traceback(e)}")
            return None
    
    async def get_user(self, username: str) -> UserResponse | None:
        """
        Получение информации о пользователе
        
        Args:
            username: Имя пользователя в Marzban
            
        Returns:
            Dict с информацией о пользователе или None
        """
        if self.api.client.is_closed:
            await self.initialize()

        token = await self.get_token()
        if not token:
            return None
        try:
            user_info = await self.api.get_user(username=username, token=token)
            return user_info
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logging.info(f"Cannot get user: {username} does not exist")
            else:
                logging.info(f"Cannot get user: {username} error: {e.response}")
            return None

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение пользователя по Telegram ID
        
        Args:
            telegram_id: Telegram ID пользователя
            
        Returns:
            Dict с информацией о пользователе или None
        """
        username = f"tg_{telegram_id}"
        return await self.get_user(username)
    
    async def modify_user(self, username: str, modifications: Dict[str, Any]) -> UserResponse | None:
        """
        Изменение данных пользователя
        
        Args:
            username: Имя пользователя в Marzban
            modifications: Словарь с изменениями
            
        Returns:
            Dict с обновленными данными пользователя или None
        """
        if self.api.client.is_closed:
            await self.initialize()

        token = await self.get_token()
        if not token:
            return None
        
        try:
            # Создаем объект UserModify из словаря изменений
            user_modify = UserModify(**modifications)
            
            modified_user = await self.api.modify_user(
                username=username, 
                user=user_modify, 
                token=token
            )
            
            logger.info(f"✅ Пользователь {username} успешно изменен")
            return modified_user
            
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.error(f"❌ Пользователь не найден для изменения: {username}")
            elif e.response.status_code == 400:
                logger.error(f"❌ Ошибка валидации при изменении пользователя {username}: {e.response.text}")
            else:
                logger.error(f"❌ Ошибка HTTP при изменении пользователя {username}: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка изменения пользователя {username}: {format_error_traceback(e)}")
            return None
    
    async def remove_user(self, username: str) -> bool:
        """
        Удаление пользователя из Marzban
        
        Args:
            username: Имя пользователя в Marzban
            
        Returns:
            True если пользователь удален, иначе False
        """
        if self.api.client.is_closed:
            await self.initialize()

        token = await self.get_token()
        if not token:
            return False
        
        try:
            await self.api.remove_user(username=username, token=token)
            logger.info(f"✅ Пользователь {username} успешно удален")
            return True
            
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.error(f"❌ Пользователь не найден для удаления: {username}")
            else:
                logger.error(f"❌ Ошибка HTTP при удалении пользователя {username}: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка удаления пользователя {username}: {format_error_traceback(e)}")
            return False
    
    async def extend_subscription(self, username: str, days: int) -> bool:
        """
        Продление подписки пользователя
        
        Args:
            username: Имя пользователя в Marzban
            days: Количество дней для продления
            
        Returns:
            True если подписка продлена, иначе False
        """
        try:
            # Получаем текущие данные пользователя
            user_data = await self.get_user(username)
            if not user_data:
                return False
            
            # Рассчитываем новое время истечения
            current_expire = user_data.expire
            new_expire = current_expire + (days * 24 * 60 * 60)  # Конвертируем дни в секунды
            
            # Обновляем пользователя
            result = await self.modify_user(username, {"expire": new_expire})
            return result is not None
            
        except Exception as e:
            logger.error(f"❌ Ошибка продления подписки пользователя {username}: {format_error_traceback(e)}")
            return False
    
    async def change_user_status(self, username: str, status: str) -> bool:
        """
        Изменение статуса пользователя
        
        Args:
            username: Имя пользователя в Marzban
            status: Новый статус ("active", "disabled", "limited")
            
        Returns:
            True если статус изменен, иначе False
        """
        return await self.modify_user(username, {"status": status}) is not None
    
    async def get_system_stats(self) -> SystemStats | None:
        """
        Получение системной статистики
        
        Returns:
            Dict со статистикой системы или None
        """
        if self.api.client.is_closed:
            await self.initialize()

        token = await self.get_token()
        if not token:
            return None
        
        try:
            stats = await self.api.get_system_stats(token=token)
            return stats
            
        except HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error(f"❌ Ошибка авторизации при получении статистики: {e.response.text}")
            else:
                logger.error(f"❌ Ошибка HTTP при получении статистики: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения системной статистики: {format_error_traceback(e)}")
            return None
    
    async def get_all_users(self, offset: int = 0, limit: int = 100) -> UsersResponse | None:
        """
        Получение списка всех пользователей
        
        Args:
            offset: Смещение для пагинации
            limit: Лимит пользователей
            
        Returns:
            List с пользователями или None
        """
        if self.api.client.is_closed:
            await self.initialize()

        token = await self.get_token()
        if not token:
            return None
        
        try:
            users = await self.api.get_users(token=token, offset=offset, limit=limit)
            return users
            
        except HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error(f"❌ Ошибка авторизации при получении списка пользователей: {e.response.text}")
            else:
                logger.error(f"❌ Ошибка HTTP при получении списка пользователей: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка пользователей: {format_error_traceback(e)}")
            return None
    
    async def get_user_usage(self, username: str, start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
        """
        Получение статистики использования трафика пользователя
        
        Args:
            username: Имя пользователя в Marzban
            start_date: Начальная дата (YYYY-MM-DD)
            end_date: Конечная дата (YYYY-MM-DD)
            
        Returns:
            Dict со статистикой использования или None
        """
        if self.api.client.is_closed:
            await self.initialize()

        token = await self.get_token()
        if not token:
            return None
        
        try:
            usage = await self.api.get_user_usage(
                token=token, 
                start=start_date, 
                end=end_date
            )
            return usage
            
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.error(f"❌ Пользователь не найден для получения статистики: {username}")
            elif e.response.status_code == 400:
                logger.error(f"❌ Ошибка валидации дат для статистики пользователя {username}: {e.response.text}")
            else:
                logger.error(f"❌ Ошибка HTTP при получении статистики пользователя {username}: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики использования пользователя {username}: {format_error_traceback(e)}")
            return None
    
    async def reset_user_usage(self, username: str) -> bool:
        """
        Сброс статистики использования пользователя
        
        Args:
            username: Имя пользователя в Marzban
            
        Returns:
            True если статистика сброшена, иначе False
        """
        if self.api.client.is_closed:
            await self.initialize()

        token = await self.get_token()
        if not token:
            return False
        
        try:
            await self.api.reset_user_data_usage(username=username, token=token)
            logger.info(f"✅ Статистика использования пользователя {username} сброшена")
            return True
            
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.error(f"❌ Пользователь не найден для сброса статистики: {username}")
            else:
                logger.error(f"❌ Ошибка HTTP при сбросе статистики пользователя {username}: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка сброса статистики пользователя {username}: {format_error_traceback(e)}")
            return False
    
    async def get_user_subscription_info(self, username: str) -> SubscriptionUserResponse | None:
        """
        Получение информации о подписке пользователя
        
        Args:
            username: Имя пользователя в Marzban
            
        Returns:
            Dict с информацией о подписке или None
        """
        if self.api.client.is_closed:
            await self.initialize()

        token = await self.get_token()
        if not token:
            return None
        
        try:
            # Сначала получаем данные пользователя
            user_data = await self.get_user(username)
            if not user_data:
                return None
            
            # Получаем подписку по URL
            subscription_url = user_data.subscription_url
            if not subscription_url:
                return None
            
            subscription_info = await self.api.get_user_subscription_info(url=subscription_url)
            return subscription_info
            
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.error(f"❌ Подписка пользователя {username} не найдена")
            else:
                logger.error(f"❌ Ошибка HTTP при получении подписки пользователя {username}: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о подписке пользователя {username}: {format_error_traceback(e)}")
            return None
    
    def _get_proxy_config(self, protocol: str) -> ProxySettings:
        """
        Получение конфигурации прокси для протокола
        
        Args:
            protocol: Протокол (vless, vmess, trojan, shadowsocks)
            
        Returns:
            ProxySettings с конфигурацией протокола
        """
        configs = {
            ProtocolType.VLESS: ProxySettings(flow="xtls-rprx-vision"),
            ProtocolType.VMESS: ProxySettings(),
            ProtocolType.TROJAN: ProxySettings(),
            ProtocolType.SHADOWSOCKS: ProxySettings(method="aes-256-gcm")
        }
        
        return configs.get(protocol, configs[ProtocolType.VLESS])
    
    async def health_check(self) -> bool:
        """
        Проверка здоровья API
        
        Returns:
            True если API доступен, иначе False
        """
        if self.api.client.is_closed:
            await self.initialize()
        
        try:
            stats = await self.get_system_stats()
            return stats is not None
        except Exception as e:
            logger.error(f"❌ Ошибка проверки здоровья API: {format_error_traceback(e)}")
            return False


# Глобальный экземпляр сервиса
marzban_service = MarzbanService()
