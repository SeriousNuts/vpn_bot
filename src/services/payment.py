import json
from datetime import datetime
from typing import Dict, Any, Optional

import httpx

from src.core.config import settings
from src.core.database import get_db_context
from src.enums import PaymentStatus
from src.enums import SubscriptionStatus
from src.models import Payment
from src.services.marzban import marzban_api


class CryptoBotAPI:
    def __init__(self):
        self.base_url = "https://pay.crypt.bot/api"
        self.token = settings.cryptobot_token
        self.provider_token = settings.cryptobot_provider_token
    
    def get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        return {"Crypto-Pay-API-Token": self.token}
    
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
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/createInvoice",
                    json=payload,
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Failed to create invoice: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                print(f"Create invoice error: {e}")
                return None
    
    async def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """Get invoice information"""
        params = {"invoice_id": invoice_id}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/getInvoices",
                    params=params,
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])
                    return items[0] if items else None
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
                    f"{self.base_url}/getBalance",
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
                    f"{self.base_url}/getExchangeRates",
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
        
        if invoice:
            return {
                "invoice_id": invoice.get("invoice_id"),
                "pay_url": invoice.get("pay_url"),
                "amount": invoice.get("amount"),
                "asset": invoice.get("asset"),
                "created_at": invoice.get("created_at")
            }
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
                        result = await marzban_api.create_user(user, subscription)
                        
                        if result:
                            # Get subscription URL
                            subscription_url = await marzban_api.get_user_subscription_url(
                                user.marzban_username
                            )
                            if subscription_url:
                                subscription.subscription_url = subscription_url
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
