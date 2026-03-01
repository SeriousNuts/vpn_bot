import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import httpx

from src.core.config import settings
from src.enums import ProtocolType
from src.models import User, Subscription
from marzban import MarzbanAPI, UserCreate, ProxySettings


class MarzbanAPISerivce:
    def __init__(self):
        self.base_url = settings.marzban_url.rstrip('/')
        self.username = settings.marzban_username
        self.password = settings.marzban_password
        self.token = None
        self.api = None
    
    async def login(self) -> bool:
        """Authenticate with Marzban API"""
        self.api = MarzbanAPI(base_url=self.base_url)
        self.token = await self.api.get_token(username=self.username, password=self.password)
    
    def get_headers(self) -> Dict[str, str]:
        """Get authorization headers"""
        return {"Authorization": f"Bearer {self.token}"}
    
    async def create_user(self, user: User, subscription: Subscription) -> UserCreate:
        """Create a new user in Marzban"""

        if not self.token or not self.api:
            if not await self.login():
                return None
        new_user = UserCreate(username=str(user.telegram_id),
                              proxies={subscription.protocol: ProxySettings(flow="xtls-rprx-vision")})
        added_user = await self.api.add_user(new_user, token=self.token.access_token)
        return added_user
    
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
marzban_api = MarzbanAPISerivce()
