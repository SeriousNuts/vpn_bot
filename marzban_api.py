import httpx
import base64
import secrets
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from config import settings
from models import User, Subscription, ProtocolType

class MarzbanAPI:
    def __init__(self):
        self.base_url = settings.marzban_url.rstrip('/')
        self.username = settings.marzban_username
        self.password = settings.marzban_password
        self.token = None
    
    async def login(self) -> bool:
        """Authenticate with Marzban API"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/admin/token",
                    data={"username": self.username, "password": self.password}
                )
                if response.status_code == 200:
                    data = response.json()
                    self.token = data.get("access_token")
                    return True
                else:
                    print(f"Login failed: {response.status_code} - {response.text}")
                    return False
            except Exception as e:
                print(f"Login error: {e}")
                return False
    
    def get_headers(self) -> Dict[str, str]:
        """Get authorization headers"""
        return {"Authorization": f"Bearer {self.token}"}
    
    async def create_user(self, user: User, subscription: Subscription) -> Optional[Dict[str, Any]]:
        """Create a new user in Marzban"""
        if not self.token:
            if not await self.login():
                return None
        
        # Generate username and password
        username = f"tg_{user.telegram_id}"
        password = secrets.token_urlsafe(12)
        
        # Calculate expiry date
        expiry_date = datetime.now() + timedelta(days=subscription.duration_days)
        
        # Create user data
        user_data = {
            "username": username,
            "password": password,
            "proxies": {
                subscription.protocol: self.get_proxy_config(subscription.protocol)
            },
            "data_limit": 0,  # 0 means unlimited
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
            "expire": int(expiry_date.timestamp()),
            "on_hold_expire_duration": 0,
            "on_hold_timeout": "12m"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/user",
                    json=user_data,
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    # Update user with Marzban credentials
                    user.marzban_username = username
                    user.marzban_password = password
                    
                    return response.json()
                else:
                    print(f"Failed to create user: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                print(f"Create user error: {e}")
                return None
    
    async def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user information from Marzban"""
        if not self.token:
            if not await self.login():
                return None
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/user/{username}",
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Failed to get user: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                print(f"Get user error: {e}")
                return None
    
    async def update_user(self, username: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update user in Marzban"""
        if not self.token:
            if not await self.login():
                return None
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(
                    f"{self.base_url}/api/user/{username}",
                    json=data,
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Failed to update user: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                print(f"Update user error: {e}")
                return None
    
    async def delete_user(self, username: str) -> bool:
        """Delete user from Marzban"""
        if not self.token:
            if not await self.login():
                return False
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.base_url}/api/user/{username}",
                    headers=self.get_headers()
                )
                
                return response.status_code == 200
                    
            except Exception as e:
                print(f"Delete user error: {e}")
                return False
    
    async def get_user_subscription_url(self, username: str) -> Optional[str]:
        """Get subscription URL for user"""
        if not self.token:
            if not await self.login():
                return None
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/user/{username}/subscription",
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    # The subscription is returned as plain text
                    return response.text
                else:
                    print(f"Failed to get subscription: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                print(f"Get subscription error: {e}")
                return None
    
    async def change_user_protocol(self, username: str, new_protocol: str) -> bool:
        """Change user's protocol"""
        if not self.token:
            if not await self.login():
                return False
        
        # Get current user data
        user_data = await self.get_user(username)
        if not user_data:
            return False
        
        # Update proxies
        user_data["proxies"] = {
            new_protocol: self.get_proxy_config(new_protocol)
        }
        
        # Update user
        result = await self.update_user(username, user_data)
        return result is not None
    
    async def extend_user_subscription(self, username: str, days: int) -> bool:
        """Extend user subscription by specified days"""
        if not self.token:
            if not await self.login():
                return False
        
        # Get current user data
        user_data = await self.get_user(username)
        if not user_data:
            return False
        
        # Calculate new expiry date
        current_expire = user_data.get("expire", 0)
        new_expire = current_expire + (days * 24 * 60 * 60)  # Convert days to seconds
        
        # Update user
        update_data = {"expire": new_expire}
        result = await self.update_user(username, update_data)
        return result is not None
    
    async def get_system_stats(self) -> Optional[Dict[str, Any]]:
        """Get system statistics"""
        if not self.token:
            if not await self.login():
                return None
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/system",
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Failed to get stats: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                print(f"Get stats error: {e}")
                return None
    
    async def get_all_users(self) -> Optional[List[Dict[str, Any]]]:
        """Get all users from Marzban"""
        if not self.token:
            if not await self.login():
                return None
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/users",
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    return response.json().get("users", [])
                else:
                    print(f"Failed to get users: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                print(f"Get users error: {e}")
                return None
    
    def get_proxy_config(self, protocol: str) -> Dict[str, Any]:
        """Get proxy configuration for a protocol"""
        configs = {
            ProtocolType.VLESS: {
                "id": secrets.token_hex(16),
                "flow": "xtls-rprx-vision"
            },
            ProtocolType.VMESS: {
                "id": secrets.token_hex(16),
                "alterId": 0
            },
            ProtocolType.TROJAN: {
                "password": secrets.token_urlsafe(32)
            },
            ProtocolType.SHADOWSOCKS: {
                "password": secrets.token_urlsafe(32),
                "method": "aes-256-gcm"
            }
        }
        return configs.get(protocol, configs[ProtocolType.VLESS])

# Global instance
marzban_api = MarzbanAPI()
