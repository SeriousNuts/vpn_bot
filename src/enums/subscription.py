from enum import Enum

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    PENDING = "pending"
    CANCELLED = "cancelled"

class ProtocolType(str, Enum):
    VLESS = "vless"
    VMESS = "vmess"
    TROJAN = "trojan"
    SHADOWSOCKS = "shadowsocks"
