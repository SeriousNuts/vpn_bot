#!/usr/bin/env python3
"""
Тестовый скрипт для проверки миграции пользователей из Marzban
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.core.config import settings
    from src.services.marzban import marzban_service
    print("✅ Импорты успешно загружены")
    print(f"🔧 Marzban URL: {settings.marzban_url}")
    
    async def test_connection():
        try:
            print("📡 Тест подключения к Marzban...")
            users = await marzban_service.get_all_users()
            print(f"✅ Подключение успешно! Найдено {len(users)} пользователей")
            
            if users:
                print("\nПервые 3 пользователя:")
                for i, user in enumerate(users[:3], 1):
                    username = user.get('username', 'unknown')
                    status = user.get('status', 'unknown')
                    print(f"   {i}. @{username} - {status}")
            else:
                print("ℹ️ Пользователи не найдены")
                
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            import traceback
            traceback.print_exc()
    
    if __name__ == "__main__":
        asyncio.run(test_connection())
        
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("Убедитесь что вы запускаете скрипт из корневой директории проекта")
    print("Или что все зависимости установлены")
