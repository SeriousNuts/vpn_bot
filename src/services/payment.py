import json
from datetime import datetime
from typing import Dict, Any, Optional

import httpx

from src.core.config import settings
from src.core.database import get_db_context
from src.enums import PaymentStatus
from src.enums import SubscriptionStatus
from src.models import Payment
from src.services.marzban import marzban_service


class CryptoBotAPI:
    def __init__(self):
        self.base_url = settings.cryptobot_url
        self.token = settings.cryptobot_token
    
    def get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        return {"Crypto-Pay-API-Token": self.token}

    async def get_me(self):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/api/getMe", headers=self.get_headers())
                print(response.json())
                return response.json()
            except Exception as e:
                print(f"Failed to get me: {e}")
                return None

    async def create_invoice(
        self, 
        amount: float, 
        description: str, 
        user_id: int,
        payment_id: int
    ) -> Optional[Dict[str, Any]]:
        """Create a new invoice"""
        payload = {
            "asset": "USDT",  # You can make this configurable
            "amount": str(amount),
            "description": description,
            "paid_btn_name": "openBot",
            "paid_btn_url": f"https://t.me/{settings.bot_username}",  # Will be set dynamically
            "payload": json.dumps({"payment_id": payment_id, "user_id": user_id}),
            "allow_comments": False,
            "allow_anonymous": False,
            "expires_in": 3600  # 1 hour expiry
        }
        await self.get_me()
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/createInvoice",
                    json=payload,
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    print(f"Created invoice: {response.json()}")
                    print(f"Created invoice status: {response.status_code}")
                    return response.json()
                else:
                    print(f"Failed to create invoice: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                print(f"Create invoice error: {e}")
                return None
    
    async def create_payment_usdt(
        self, 
        amount: float, 
        description: str, 
        user_id: int, 
        payment_id: int
    ) -> Optional[Dict[str, Any]]:
        """Create a new invoice with USDT"""
        payload = {
            "asset": "USDT",
            "amount": str(amount),
            "description": description,
            "paid_btn_name": "openBot",
            "paid_btn_url": f"https://t.me/{settings.bot_username}",
            "payload": json.dumps({"payment_id": payment_id, "user_id": user_id}),
            "allow_comments": False,
            "allow_anonymous": False,
            "expires_in": 3600  # 1 hour expiry
        }
        await self.get_me()
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/createInvoice",
                    json=payload,
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    print(f"Created USDT invoice: {response.json()}")
                    return response.json()
                else:
                    print(f"Failed to create USDT invoice: {response.status_code} - {response.text}")
                    return None
            except Exception as e:
                print(f"Error creating USDT invoice: {e}")
                return None

    async def create_payment_ton(
        self, 
        amount: float, 
        description: str, 
        user_id: int,
        payment_id: int
    ) -> Optional[Dict[str, Any]]:
        """Create a new payment with TON"""
        payload = {
            "asset": "TON",
            "amount": str(amount),
            "description": description,
            "paid_btn_name": "openBot",
            "paid_btn_url": f"https://t.me/{settings.bot_username}",
            "payload": json.dumps({"payment_id": payment_id, "user_id": user_id}),
            "allow_comments": False,
            "allow_anonymous": False,
            "expires_in": 3600  # 1 hour expiry
        }
        
        print(f"TON payment payload: {payload}")
        await self.get_me()
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/createInvoice",
                    json=payload,
                    headers=self.get_headers()
                )
                
                print(f"TON API response status: {response.status_code}")
                print(f"TON API response headers: {response.headers}")
                print(f"TON API response text: {response.text}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"Created TON invoice: {result}")
                    
                    # Проверяем структуру ответа
                    if result.get('ok'):
                        result_data = result.get("result")
                        print(f"TON result_data: {result_data}")
                        print(f"TON result_data type: {type(result_data)}")
                        print(f"TON result_data keys: {list(result_data.keys()) if result_data else 'None'}")
                        
                        if result_data and isinstance(result_data, dict) and len(result_data) > 0:
                            return {
                                "ok": True,
                                "invoice_id": str(result_data.get("invoice_id")),
                                "pay_url": result_data.get("pay_url"),
                                "amount": result_data.get("amount"),
                                "asset": result_data.get("asset"),
                                "created_at": result_data.get("created_at")
                            }
                        else:
                            error_msg = f"Empty or invalid result data: {result_data}"
                            print(f"Error: {error_msg}")
                            return {"ok": False, "error": error_msg}
                    else:
                        error_msg = f"Unexpected response format: {result}"
                        print(f"Error: {error_msg}")
                        return {"ok": False, "error": error_msg, "response": result}
                        
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    print(f"Error: {error_msg}")
                    return {"ok": False, "error": error_msg}
            except Exception as e:
                error_msg = f"Exception: {str(e)}"
                print(f"Error: {error_msg}")
                return {"ok": False, "error": error_msg}
    
    async def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """Get invoice information"""
        params = {"invoice_id": invoice_id}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/getInvoices",
                    params=params,
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        items = data.get("result").get("items", [])
                        return items[0] if items else None
                    else:
                        print(f"Failed to get invoice result is not ok: {response.status_code} - {response.text}")
                        return None
                else:
                    print(f"Failed to get invoice: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                print(f"Get invoice error: {e}")
                return None
    
    async def verify_payment(self, invoice_data: Dict[str, Any]) -> bool:
        """Verify payment webhook signature"""
        # This is used for webhook verification
        # Implementation depends on how you receive webhooks
        pass
    
    async def check_payment_status(self, invoice_id: str) -> Optional[str]:
        """Check payment status"""
        invoice = await self.get_invoice(invoice_id)
        if invoice:
            return invoice.get("status")
        return None
    
    async def get_balance(self) -> Optional[Dict[str, Any]]:
        """Get account balance"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/getBalance",
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Failed to get balance: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                print(f"Get balance error: {e}")
                return None
    
    async def get_exchange_rates(self) -> Optional[Dict[str, Any]]:
        """Get exchange rates"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/getExchangeRates",
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Failed to get exchange rates: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                print(f"Get exchange rates error: {e}")
                return None

class PaymentProcessor:
    def __init__(self):
        self.cryptobot = CryptoBotAPI()
    
    async def create_payment(
        self, 
        amount: float, 
        description: str, 
        user_id: int,
        payment_id: int
    ) -> Optional[Dict[str, Any]]:
        """Create a new payment"""
        invoice = await self.cryptobot.create_invoice(
            amount=amount,
            description=description,
            user_id=user_id,
            payment_id=payment_id
        )
        print(f"Created payment on payment processor: {invoice}")
        if invoice and invoice.get('ok'):
            return {
                "invoice_id": invoice.get("result").get("id"),
                "pay_url": invoice.get("result").get("pay_url"),
                "amount": invoice.get("result").get("amount"),
                "asset": invoice.get("result").get("asset"),
                "created_at": invoice.get("result").get("created_at")
            }
        return None
    
    async def create_payment_usdt(
        self, 
        amount: float, 
        description: str, 
        user_id: int,
        payment_id: int
    ) -> Optional[Dict[str, Any]]:
        """Create a new payment with USDT"""
        invoice = await self.cryptobot.create_payment_usdt(
            amount=amount,
            description=description,
            user_id=user_id,
            payment_id=payment_id
        )
        print(f"Created USDT payment on payment processor: {invoice}")
        if invoice and invoice.get('ok'):
            return {
                "invoice_id": invoice.get("result").get("id"),
                "pay_url": invoice.get("result").get("pay_url"),
                "amount": invoice.get("result").get("amount"),
                "asset": invoice.get("result").get("asset"),
                "created_at": invoice.get("result").get("created_at")
            }
        return None

    async def create_payment_ton(
        self, 
        amount: float, 
        description: str, 
        user_id: int,
        payment_id: int
    ) -> Optional[Dict[str, Any]]:
        """Create a new payment with TON"""
        invoice = await self.cryptobot.create_payment_ton(
            amount=amount,
            description=description,
            user_id=user_id,
            payment_id=payment_id
        )
        print(f"Created TON payment on payment processor: {invoice}")
        
        # Проверяем формат ответа от CryptoBotAPI
        if invoice and invoice.get('ok'):
            # Данные уже правильно обработаны в CryptoBotAPI
            return invoice
        elif invoice and "error" in invoice:
            print(f"Error in TON invoice response: {invoice}")
            return {"ok": False, "error": invoice.get("error")}
        else:
            print(f"Unexpected TON invoice response format: {invoice}")
            return {"ok": False, "error": "Unexpected response format", "response": invoice}
            
        return None

    async def check_payment(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """Check payment status"""
        invoice = await self.cryptobot.get_invoice(invoice_id)
        
        if invoice:
            return {
                "invoice_id": invoice.get("invoice_id"),
                "status": invoice.get("status"),
                "amount": invoice.get("amount"),
                "asset": invoice.get("asset"),
                "paid_at": invoice.get("paid_at"),
                "payload": invoice.get("payload")
            }
        return None
    
    async def process_payment_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """Process payment webhook from CryptoBot"""
        try:
            # Extract payload
            payload = json.loads(webhook_data.get("payload", "{}"))
            payment_id = payload.get("payment_id")
            user_id = payload.get("user_id")
            
            if not payment_id or not user_id:
                return False
            
            # Check payment status
            invoice_id = webhook_data.get("invoice_id")
            payment_info = await self.check_payment(invoice_id)
            
            if not payment_info:
                return False
            
            # Update payment in database
            async with get_db_context() as db:
                payment = await db.get(Payment, payment_id)
                if not payment:
                    return False
                
                if payment_info["status"] == "paid":
                    payment.status = PaymentStatus.COMPLETED
                    payment.completed_at = datetime.now()
                    payment.payment_id = invoice_id
                    
                    # Activate subscription
                    subscription = payment.subscription
                    if subscription:
                        subscription.status = SubscriptionStatus.ACTIVE
                        subscription.started_at = datetime.now()
                        
                        # Create VPN user in Marzban
                        user = payment.user
                        result = await marzban_service.create_user(user, subscription)
                        
                        if result and result.subscription_url:
                                subscription.subscription_url = result.subscription_url
                                subscription.config_data = result
                    
                    await db.commit()
                    return True
                
                elif payment_info["status"] == "expired":
                    payment.status = PaymentStatus.FAILED
                    await db.commit()
                    return True
                
        except Exception as e:
            print(f"Process webhook error: {e}")
            return False
        
        return False

# Global instance
payment_processor = PaymentProcessor()
