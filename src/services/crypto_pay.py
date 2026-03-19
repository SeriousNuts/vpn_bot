"""
Сервис для работы с Crypto Pay API
Поддерживает создание инвойсов с автоматическим пересчетом фиатных валют в криптовалюту
"""

import logging
from typing import Dict, Optional, Any
import aiohttp
import json

logger = logging.getLogger(__name__)


class CryptoPayService:
    """Сервис для работы с Crypto Pay API"""
    
    def __init__(self, token: str, api_url: str = "https://pay.crypt.bot/api"):
        self.token = token
        # Поддерживаем как mainnet так и testnet URL
        if "testnet" in api_url:
            self.api_url = api_url
        else:
            self.api_url = api_url
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получить или создать сессию"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def _make_request(self, method: str, params: Dict[str, Any]) -> Optional[Dict]:
        """Выполнить запрос к API"""
        try:
            session = await self._get_session()
            url = f"{self.api_url}/{method}"
            
            headers = {
                "Crypto-Pay-API-Token": self.token,
                "Content-Type": "application/json"
            }
            
            async with session.post(url, json=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok"):
                        return data.get("result")
                    else:
                        logger.error(f"Crypto Pay API error: {data.get('error')}")
                        return None
                else:
                    logger.error(f"HTTP error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Crypto Pay API request failed: {e}")
            return None
    
    async def create_invoice(
        self,
        amount: float,
        description: str,
        fiat: str = "USD",
        accepted_assets: str = "USDT,TON,BTC,ETH,LTC,BNB,TRX,USDC",
        swap_to: Optional[str] = None,
        expires_in: int = 900,
        payload: Optional[str] = None,
        allow_comments: bool = True,
        allow_anonymous: bool = True
    ) -> Optional[Dict]:
        """
        Создать инвойс с автоматическим пересчетом из фиатной валюты
        
        Args:
            amount: Сумма в фиатной валюте (USD)
            description: Описание платежа
            fiat: Фиатная валюта (USD, EUR и т.д.)
            accepted_assets: Разрешенные криптовалюты для оплаты
            swap_to: Куда конвертировать после оплаты
            expires_in: Время жизни инвойса в секундах
            payload: Данные для привязки к платежу
            allow_comments: Разрешить комментарии
            allow_anonymous: Разрешить анонимные платежи
            
        Returns:
            Dict с информацией об инвойсе или None в случае ошибки
        """
        params = {
            "currency_type": "fiat",
            "fiat": fiat,
            "amount": str(amount),
            "description": description,
            "accepted_assets": accepted_assets,
            "expires_in": expires_in,
            "allow_comments": allow_comments,
            "allow_anonymous": allow_anonymous
        }
        
        if swap_to:
            params["swap_to"] = swap_to
            
        if payload:
            params["payload"] = payload
        
        logger.info(f"Creating Crypto Pay invoice: {params}")
        result = await self._make_request("createInvoice", params)
        
        if result:
            logger.info(f"Crypto Pay invoice created: {result.get('invoice_id')}")
        else:
            logger.error("Failed to create Crypto Pay invoice")
            
        return result
    
    async def get_invoices(self, asset: Optional[str] = None, status: Optional[str] = None) -> Optional[Dict]:
        """Получить список инвойсов"""
        params = {}
        if asset:
            params["asset"] = asset
        if status:
            params["status"] = status
            
        return await self._make_request("getInvoices", params)
    
    async def get_invoice(self, invoice_id: int) -> Optional[Dict]:
        """Получить информацию об инвойсе по ID"""
        params = {"invoice_id": invoice_id}
        return await self._make_request("getInvoices", params)
    
    async def get_balance(self) -> Optional[Dict]:
        """Получить баланс"""
        return await self._make_request("getBalance", {})
    
    async def get_exchange_rates(self) -> Optional[Dict]:
        """Получить курсы обмена"""
        return await self._make_request("getExchangeRates", {})
    
    async def close(self):
        """Закрыть сессию"""
        if self.session and not self.session.closed:
            await self.session.close()


# Глобальный экземпляр сервиса
crypto_pay_service: Optional[CryptoPayService] = None


def get_crypto_pay_service() -> Optional[CryptoPayService]:
    """Получить глобальный экземпляр сервиса"""
    return crypto_pay_service


def init_crypto_pay_service(token: str, api_url: str = "https://pay.crypt.bot/api") -> CryptoPayService:
    """Инициализировать глобальный экземпляр сервиса"""
    global crypto_pay_service
    crypto_pay_service = CryptoPayService(token, api_url)
    return crypto_pay_service
