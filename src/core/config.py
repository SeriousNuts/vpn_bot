import os
from typing import Dict, List
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()
print("Environment loaded")
class Settings(BaseSettings):
    # Telegram Bot Configuration
    bot_token: str = Field(..., env="BOT_TOKEN")
    admin_id: int = Field(..., env="ADMIN_ID")
    support_username: str = Field(..., env="SUPPORT_USERNAME")
    
    # Database Configuration
    database_url: str = Field(..., env="DATABASE_URL")
    
    # Marzban API Configuration
    marzban_url: str = Field(..., env="MARZBAN_URL")
    marzban_username: str = Field(..., env="MARZBAN_USERNAME")
    marzban_password: str = Field(..., env="MARZBAN_PASSWORD")
    
    # CryptoBot Configuration
    cryptobot_token: str = Field(..., env="CRYPTOBOT_TOKEN")
    cryptobot_provider_token: str = Field(..., env="CRYPTOBOT_PROVIDER_TOKEN")
    
    # Redis Configuration (optional)
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    
    # Logging Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="logs/bot.log", env="LOG_FILE")
    
    # Security
    secret_key: str = Field(default="your-secret-key-here", env="SECRET_KEY")
    
    # Эти поля будем заполнять отдельно
    subscription_prices: Dict[str, float] = {
        "1_month": 10.0, 
        "3_months": 25.0, 
        "6_months": 45.0, 
        "1_year": 80.0
    }
    #expiry_notification_days: List[int] = [3, 1]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

# Создаем экземпляр настроек
settings = Settings()

prices_str = os.getenv("SUBSCRIPTION_PRICES", "")
if prices_str:
    try:
        # Пробуем распарсить как JSON
        import json
        settings.subscription_prices = json.loads(prices_str)
    except:
        try:
            # Пробуем распарсить как key=value
            result = {}
            pairs = prices_str.split(",")
            for pair in pairs:
                if "=" in pair:
                    key, value = pair.split("=")
                    result[key.strip()] = float(value.strip())
                elif ":" in pair:
                    key, value = pair.split(":")
                    result[key.strip()] = float(value.strip())
            if result:
                settings.subscription_prices = result
        except:
            pass  # оставляем значение по умолчанию