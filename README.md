# VPN Bot - Telegram VPN Subscription Service

A comprehensive Telegram bot for selling VPN subscriptions on Marzban with CryptoBot payment integration.

## Features

### User Features
- 📱 **User Registration** - Simple registration with phone and email
- 💰 **Subscription Purchase** - Multiple plans with CryptoBot payment
- 🔧 **Protocol Selection** - Support for VLESS, VMESS, Trojan, Shadowsocks
- 📊 **Subscription Management** - View status, change protocols, renew
- ⏰ **Expiry Notifications** - Automatic reminders before expiration
- 🆘 **Support System** - Contact support team directly

### Admin Features
- 🔧 **Admin Panel** - Full control over users and subscriptions
- 👥 **User Management** - View, ban, unban users
- 💳 **Payment Tracking** - Monitor all transactions
- 📊 **Statistics** - Detailed system statistics
- ⏰ **Subscription Control** - Extend, modify, deactivate subscriptions
- 📢 **Broadcast System** - Send messages to all users

### Payment Features
- 💳 **CryptoBot Integration** - Accept USDT payments
- 🔒 **Secure Processing** - Webhook verification
- 📈 **Payment Tracking** - Complete payment history
- 🔄 **Auto-Activation** - Instant subscription activation

### VPN Features
- 🌐 **Marzban Integration** - Full API integration
- 🔄 **Protocol Switching** - Change VPN protocols instantly
- 📱 **Configuration URLs** - Easy client setup
- ⚙️ **User Management** - Automatic VPN user creation/deletion

## Installation

### Prerequisites
- Python 3.8+
- PostgreSQL database
- Marzban panel
- CryptoBot account

### Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd vpn_bot
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**
```bash
cp .env.example .env
```

Edit `.env` file with your settings:
```env
# Telegram Bot Configuration
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_ID=your_admin_telegram_id_here
SUPPORT_USERNAME=your_support_username

# Database Configuration
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/vpn_bot

# Marzban API Configuration
MARZBAN_URL=https://your-marzban-domain.com
MARZBAN_USERNAME=admin
MARZBAN_PASSWORD=your_marzban_password

# CryptoBot Configuration
CRYPTOBOT_TOKEN=your_cryptobot_api_token
CRYPTOBOT_PROVIDER_TOKEN=your_cryptobot_provider_token

# Payment Configuration
SUBSCRIPTION_PRICES={"1_month": 10.0, "3_months": 25.0, "6_months": 45.0, "1_year": 80.0}

# Notification Settings
EXPIRY_NOTIFICATION_DAYS=3,1
```

4. **Initialize database**
```bash
python -c "from database import init_db; import asyncio; asyncio.run(init_db())"
```

5. **Run the bot**
```bash
python bot.py
```

## Configuration

### Telegram Bot Setup
1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Get the bot token
3. Set up commands and descriptions

### Marzban Setup
1. Install and configure Marzban panel
2. Create admin user for API access
3. Configure inbound protocols

### CryptoBot Setup
1. Create a CryptoBot account
2. Get API tokens
3. Configure payment methods

## Usage

### For Users
1. Start the bot with `/start`
2. Complete registration
3. Choose subscription plan
4. Select protocol
5. Complete payment
6. Get VPN configuration

### For Admins
1. Access admin panel (only admin ID)
2. Manage users and subscriptions
3. Monitor payments
4. Send broadcasts
5. View statistics

## Architecture

```
vpn_bot/
├── bot.py              # Main bot application
├── models.py           # Database models
├── database.py         # Database connection
├── config.py           # Configuration settings
├── marzban_api.py      # Marzban API integration
├── cryptobot_payment.py # CryptoBot payment system
├── notifications.py    # Notification service
├── admin_panel.py      # Admin panel functionality
├── requirements.txt    # Python dependencies
├── .env.example       # Environment variables example
└── README.md          # This file
```

## Database Schema

### Users Table
- User information and authentication
- Marzban credentials
- Status management

### Subscriptions Table
- Subscription plans and pricing
- Protocol configurations
- Expiry tracking

### Payments Table
- Payment transactions
- Status tracking
- External payment IDs

### Notification Logs
- Sent notifications
- Error tracking

### Admin Actions
- Admin activity logging
- Audit trail

## API Integrations

### Marzban API
- User creation/deletion
- Subscription management
- Protocol switching
- Statistics retrieval

### CryptoBot API
- Invoice creation
- Payment verification
- Balance checking

## Security Features

- 🔒 Secure API authentication
- 🛡️ Input validation
- 📝 Activity logging
- 🔐 Admin access control
- 🚫 SQL injection prevention

## Monitoring

- 📊 User statistics
- 💰 Revenue tracking
- ⚠️ Error logging
- 📈 Performance metrics

## Support

For support and questions:
- 📧 Contact: @your_support_username
- 📖 Documentation: Check this README
- 🐛 Issues: Report via GitHub issues

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Disclaimer

This software is provided "as-is" without warranty. Use at your own risk.

## Changelog

### v1.0.0
- Initial release
- Basic functionality
- CryptoBot integration
- Marzban API integration
- Admin panel
- Notification system
