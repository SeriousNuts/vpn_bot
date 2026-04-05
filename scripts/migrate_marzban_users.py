#!/usr/bin/env python3
"""
Скрипт для миграции пользователей из Marzban в базу данных бота
Выгружает всех существующих пользователей Marzban и добавляет их в бота
"""

import asyncio
import logging
import os
import sys
from typing import List, Dict, Optional, Any

from marzban import UsersResponse, UserResponse

from utils.format_error import format_error_traceback

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.database import init_db, get_db_context
from src.core.database_manager import UserRepository, user_repo
from src.services.marzban import MarzbanService
from src.models import User
from utils.logger import setup_logging

# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)


class MarzbanMigrator:
    """Класс для миграции пользователей из Marzban в бота"""
    
    def __init__(self):
        self.user_repo = None
        self.marzban_service = MarzbanService()
    
    async def initialize(self):
        """Инициализация базы данных"""
        await init_db()
        self.user_repo = user_repo
    
    async def get_marzban_users(self) -> UsersResponse | None | list[Any]:
        """Получить всех пользователей из Marzban"""
        try:
            logger.info("Получение пользователей из Marzban...")
            users = await self.marzban_service.get_all_users()
            logger.info(f"Получено {len(users.users)} пользователей из Marzban")
            return users
        except Exception as e:
            logger.error(f"Ошибка при получении пользователей из Marzban: {format_error_traceback(e)}")
            return []
    
    async def check_user_exists(self, telegram_id: int) -> Optional[User]:
        """Проверить существует ли пользователь в боте"""
        try:
            return await self.user_repo.get_user_by_telegram_id(telegram_id)
        except Exception as e:
            logger.error(f"Ошибка при проверке пользователя {telegram_id}: {format_error_traceback(e)}")
            return None
    
    async def create_user_from_marzban(self, marzban_user: UserResponse) -> Optional[User]:
        """Создать пользователя в боте на основе данных из Marzban"""
        try:
            # Извлекаем данные из Marzban пользователя
            username = marzban_user.username
            if not username:
                logger.warning(f"⚠Пропускаем пользователя без username: {marzban_user}")
                return None
            
            # Пробуем извлечь telegram_id из различных полей
            telegram_id = None
            
            # Способ 1: telegram_id
            if "telegram_id" in marzban_user:
                telegram_id = None
            
            if not telegram_id:
                logger.warning(f"Не удалось определить telegram_id для пользователя {username}")
                # Создаем пользователя с временным telegram_id на основе username
                try:
                    telegram_id = hash(username) % 1000000000  # Генерируем временный ID
                    logger.info(f"Создан временный telegram_id {telegram_id} для пользователя {username}")
                except:
                    logger.error(f"Не удалось создать временный telegram_id для {username}")
                    return None
            
            # Проверяем что telegram_id является числом
            try:
                telegram_id = int(telegram_id)
            except (ValueError, TypeError):
                logger.warning(f" Некорректный telegram_id {telegram_id} для пользователя {username}")
                return None
            
            # Проверяем что пользователь еще не существует
            existing_user = await self.check_user_exists(telegram_id)
            if existing_user:
                logger.info(f"Пользователь {telegram_id} уже существует в боте, пропускаем")
                return existing_user
            
            # Создаем пользователя в боте
            user_data = {
                "telegram_id": telegram_id,
                "marzban_username": username,
                "status": "active" if marzban_user.status == "active" else "expired"
            }
            
            user = await self.user_repo.create_user(**user_data)
            logger.info(f"Создан пользователь: telegram_id={telegram_id}, username={username}")
            return user
            
        except Exception as e:
            logger.error(f"Ошибка при создании пользователя из Marzban: {format_error_traceback(e)}")
            return None
    
    async def migrate_all_users(self) -> Dict[str, int]:
        """Мигрировать всех пользователей из Marzban в бота"""
        logger.info("Начинаем миграцию пользователей из Marzban в бота...")
        
        # Получаем пользователей из Marzban
        marzban_users = await self.get_marzban_users()
        if not marzban_users:
            logger.warning("Не удалось получить пользователей из Marzban")
            return {"total": 0, "migrated": 0, "skipped": 0, "errors": 0}
        
        stats = {
            "total": marzban_users.total,
            "migrated": 0,
            "skipped": 0,
            "errors": 0
        }
        
        # Мигрируем каждого пользователя
        for marzban_user in marzban_users.users:
            try:
                username = marzban_user.username
                logger.info(f"Обработка пользователя: {username}")
                
                # Пробуем создать пользователя
                user = await self.create_user_from_marzban(marzban_user)
                
                if user:
                    stats["migrated"] += 1
                else:
                    stats["errors"] += 1
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке пользователя {marzban_user.username}: {e}")
                stats["errors"] += 1
        
        logger.info(" Статистика миграции:")
        logger.info(f"   Всего пользователей: {stats['total']}")
        logger.info(f"   Успешно мигрировано: {stats['migrated']}")
        logger.info(f"   Пропущено: {stats['skipped']}")
        logger.info(f"   Ошибок: {stats['errors']}")
        
        return stats
    
    async def show_marzban_users(self):
        """Показать информацию о пользователях в Marzban"""
        users_object = await self.get_marzban_users()
        # вытаскиваем список из объекта
        users = users_object.users
        if not users:
            return
        
        logger.info("Пользователи в Marzban:")
        for i, user in enumerate(users, 1):
            username = user.username
            status = user.status
            expire = user.expire
            logger.info(f"   {i}. {username} - {status} - expire: {expire}")
        
        if len(users) > 10:
            logger.info(f"   ... и еще {len(users) - 10} пользователей")


async def main():
    """Главная функция"""
    logger.info("Скрипт миграции пользователей из Marzban в бота")
    
    try:
        # Инициализация
        migrator = MarzbanMigrator()
        await migrator.initialize()
        
        # Показываем информацию о пользователях в Marzban
        await migrator.show_marzban_users()
        
        # Спрашиваем подтверждение
        print("\n" + "="*50)
        print(" ВНИМАНИЕ!")
        print("Этот скрипт создаст пользователей в боте на основе данных из Marzban.")
        print("Убедитесь что вы понимаете что делаете.")
        print("="*50)
        
        confirm = input("\nПродолжить миграцию? (y/N): ").lower().strip()
        if confirm != 'y':
            logger.info("❌ Миграция отменена пользователем")
            return
        
        # Выполняем миграцию
        stats = await migrator.migrate_all_users()
        
        # Показываем результат
        print("\n" + "="*50)
        print("📊 РЕЗУЛЬТАТЫ МИГРАЦИИ:")
        print(f"   Всего пользователей: {stats['total']}")
        print(f"   Успешно мигрировано: {stats['migrated']}")
        print(f"   Пропущено: {stats['skipped']}")
        print(f"   Ошибок: {stats['errors']}")
        print("="*50)
        
        if stats['migrated'] > 0:
            logger.info("Миграция успешно завершена!")
        else:
            logger.warning("Ни один пользователь не был мигрирован")
        
    except KeyboardInterrupt:
        logger.info("Миграция прервана пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка при миграции: {format_error_traceback(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
