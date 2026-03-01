import json
from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram Bot Configuration
    bot_token: str = Field(..., validation_alias="BOT_TOKEN")
    admin_id: int = Field(..., validation_alias="ADMIN_ID")
    support_username: str = Field(..., validation_alias="SUPPORT_USERNAME")
    bot_username: str = Field(..., validation_alias="BOT_USERNAME")

    # Database Configuration
    database_url: str = Field(..., validation_alias="DATABASE_URL")
    init_db: bool = Field(..., validation_alias="INIT_DB")


    # Marzban API Configuration
    marzban_url: str = Field(..., validation_alias="MARZBAN_URL")
    marzban_username: str = Field(..., validation_alias="MARZBAN_USERNAME")
    marzban_password: str = Field(..., validation_alias="MARZBAN_PASSWORD")

    # CryptoBot Configuration
    cryptobot_token: str = Field(..., validation_alias="CRYPTOBOT_TOKEN")
    cryptobot_provider_token: str = Field(..., validation_alias="CRYPTOBOT_PROVIDER_TOKEN")

    # Payment Configuration
    subscription_prices: Dict[str, float] = Field(..., validation_alias="SUBSCRIPTION_PRICES")

    # Notification Settings
    expiry_notification_days: list[int] = Field(..., validation_alias="EXPIRY_NOTIFICATION_DAYS", )

    # Redis Configuration (optional)
    redis_url: str = Field(default="redis://localhost:6379", validation_alias="REDIS_URL")

    # Logging Configuration
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_file: str = Field(default="logs/bot.log", validation_alias="LOG_FILE")

    # Security
    secret_key: str = Field(default="your-secret-key-here", validation_alias="SECRET_KEY")

    @classmethod
    def parse_expiry_days(cls, v):
        """Парсит строку вида '3,1' в список [3, 1]"""
        if isinstance(v, str):
            if not v.strip():
                return [3, 1]  # значение по умолчанию
            try:
                return [int(x.strip()) for x in v.split(',') if x.strip()]
            except ValueError as e:
                raise ValueError(f"Не удалось преобразовать '{v}' в список чисел: {e}")
        return v

    @classmethod
    def parse_subscription_prices(cls, v):
        """Парсит JSON строку вида '{"1_month": 10.0, "3_months": 25.0}' в словарь"""
        if isinstance(v, str):
            if not v.strip():
                return {"1_month": 10.0, "3_months": 25.0, "6_months": 45.0, "1_year": 80.0}
            try:
                # Пытаемся распарсить как JSON
                return json.loads(v)
            except json.JSONDecodeError:
                # Альтернативный формат: ключ=значение через запятую
                try:
                    result = {}
                    pairs = v.split(',')
                    for pair in pairs:
                        if ':' in pair:
                            key, value = pair.split(':')
                        elif '=' in pair:
                            key, value = pair.split('=')
                        else:
                            continue
                        result[key.strip()] = float(value.strip())
                    return result
                except Exception as e:
                    raise ValueError(f"Не удалось преобразовать '{v}' в словарь цен: {e}")
        return v

    @classmethod
    def parse_admin_id(cls, v):
        """Преобразует строку в int для admin_id"""
        if isinstance(v, str):
            try:
                return int(v.strip())
            except ValueError:
                raise ValueError(f"ADMIN_ID должен быть числом, получено: {v}")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Игнорировать лишние поля в .env
        case_sensitive = False  # Не учитывать регистр переменных окружения


# Создаем экземпляр настроек
settings = Settings()

# Для отладки можно добавить:
if __name__ == "__main__":
    print("Settings loaded successfully!")
    print(f"Bot Token: {'*' * len(settings.bot_token)}")  # Скрываем токен
    print(f"Admin ID: {settings.admin_id}")
    print(f"Support Username: {settings.support_username}")
    print(f"Expiry Notification Days: {settings.expiry_notification_days}")
    print(f"Subscription Prices: {settings.subscription_prices}")