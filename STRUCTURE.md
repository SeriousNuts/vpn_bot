# VPN Bot - Project Structure

This document describes the improved folder structure for the VPN Bot project.

## 📁 Project Structure

```
vpn_bot/
├── 📄 Main Files
│   ├── main.py                 # Application entry point
│   ├── setup.py                # Database initialization
│   ├── requirements.txt        # Python dependencies
│   ├── Dockerfile             # Production container
│   ├── Dockerfile.dev         # Development container
│   ├── docker-compose.yml     # Standard deployment
│   ├── docker-compose.dev.yml # Development deployment
│   ├── docker-compose.prod.yml # Production deployment
│   ├── Makefile               # Build and deployment commands
│   └── alembic.ini            # Database migration config
│
├── 📁 src/                    # Source code (Python package)
│   ├── __init__.py           # Package initialization
│   ├── bot.py                # Main bot application
│   │
│   ├── 📁 core/              # Core functionality
│   │   ├── __init__.py
│   │   ├── config.py         # Configuration management
│   │   └── database.py       # Database connection
│   │
│   ├── 📁 models/            # Database models
│   │   ├── __init__.py
│   │   ├── base.py           # Base model class
│   │   ├── user.py           # User model
│   │   ├── subscription.py   # Subscription model
│   │   ├── payment.py        # Payment model
│   │   ├── notification.py   # Notification model
│   │   └── admin.py          # Admin action model
│   │
│   ├── 📁 enums/             # Enumerations
│   │   ├── __init__.py
│   │   ├── user.py           # User status enums
│   │   ├── subscription.py   # Subscription enums
│   │   └── payment.py        # Payment enums
│   │
│   ├── 📁 services/          # Business logic services
│   │   ├── __init__.py
│   │   ├── marzban.py        # Marzban API integration
│   │   ├── payment.py        # Payment processing
│   │   └── notification.py   # Notification service
│   │
│   ├── 📁 handlers/          # Telegram bot handlers
│   │   ├── __init__.py
│   │   ├── user.py           # User message handlers
│   │   └── admin.py          # Admin message handlers
│   │
│   └── 📁 middleware/        # Bot middleware
│       ├── __init__.py
│       └── logging.py        # Logging and security middleware
│
├── 📁 utils/                 # Utility functions
│   ├── __init__.py
│   ├── helpers.py           # General helper functions
│   ├── validators.py       # Input validation
│   ├── decorators.py       # Function decorators
│   └── logger.py           # Logging configuration
│
├── 📁 migrations/           # Database migrations
│   ├── __init__.py
│   ├── env.py              # Alembic environment
│   └── script.py.mako      # Migration template
│
├── 📁 scripts/             # Utility scripts
│   ├── __init__.py
│   ├── create_admin.py     # Create admin user
│   ├── db_backup.py        # Database backup
│   └── migrate.py          # Run migrations
│
├── 📁 tests/               # Test files (ignored by git)
│   └── __init__.py
│
├── 📁 logs/                # Application logs
├── 📁 nginx/               # Nginx configuration (production)
│   └── ssl/                # SSL certificates
│
├── 📄 Configuration Files
│   ├── .env.example        # Environment variables template
│   ├── .env                 # Environment variables (git-ignored)
│   ├── .gitignore          # Git ignore rules
│   ├── .dockerignore       # Docker ignore rules
│   └── docker-entrypoint.sh # Container startup script
│
└── 📄 Documentation
    ├── README.md            # Main documentation
    ├── DOCKER.md            # Docker deployment guide
    └── STRUCTURE.md         # This file
```

## 🏗️ Architecture Overview

### **Core Components**

#### **`src/core/`** - Core Infrastructure
- **`config.py`** - Centralized configuration using Pydantic
- **`database.py`** - Database connection and session management

#### **`src/models/`** - Data Models
- **`base.py`** - SQLAlchemy base model
- **`user.py`** - User entity and relationships
- **`subscription.py`** - Subscription management
- **`payment.py`** - Payment transactions
- **`notification.py`** - Notification logging
- **`admin.py`** - Admin action tracking

#### **`src/enums/`** - Enumerations
- **`user.py`** - User status (ACTIVE, INACTIVE, BANNED)
- **`subscription.py`** - Subscription status and protocols
- **`payment.py`** - Payment status tracking

### **Business Logic**

#### **`src/services/`** - Service Layer
- **`marzban.py`** - Marzban VPN API integration
- **`payment.py`** - CryptoBot payment processing
- **`notification.py`** - Automated notifications

#### **`src/handlers/`** - Bot Handlers
- **`user.py`** - User interaction handlers
- **`admin.py`** - Admin panel handlers

### **Supporting Components**

#### **`src/middleware/`** - Request Processing
- **`logging.py`** - Request logging, error handling, security

#### **`utils/`** - Utilities
- **`helpers.py`** - Common helper functions
- **`validators.py`** - Input validation utilities
- **`decorators.py`** - Function decorators (admin_required, etc.)
- **`logger.py`** - Logging configuration

#### **`migrations/`** - Database Schema Management
- **`env.py`** - Alembic environment configuration
- **`script.py.mako`** - Migration template

#### **`scripts/`** - Management Scripts
- **`create_admin.py`** - Create admin users
- **`db_backup.py`** - Database backup utility
- **`migrate.py`** - Run database migrations

## 🔄 Data Flow

```
User Input → Middleware → Handler → Service → Model → Database
     ↓              ↓          ↓         ↓        ↓
   Logging    Validation  Business  Data     Storage
   Security   Rate Limit  Logic    Mapping  PostgreSQL
```

## 🚀 Deployment Structure

### **Development**
```bash
make dev              # Start development environment
make dev-logs         # View development logs
make dev-shell        # Access development container
```

### **Production**
```bash
make prod             # Start production environment
make prod-logs        # View production logs
make prod-shell       # Access production container
```

## 📦 Package Dependencies

### **Core Dependencies**
- `aiogram` - Telegram bot framework
- `sqlalchemy` - Database ORM
- `asyncpg` - PostgreSQL async driver
- `pydantic` - Configuration management
- `httpx` - HTTP client for API calls

### **Additional Dependencies**
- `apscheduler` - Task scheduling
- `alembic` - Database migrations
- `python-dotenv` - Environment variable loading

## 🔧 Configuration Management

### **Environment Variables**
```env
BOT_TOKEN=your_bot_token
ADMIN_ID=your_admin_id
DATABASE_URL=postgresql+asyncpg://...
MARZBAN_URL=https://your-marzban.com
CRYPTOBOT_TOKEN=your_cryptobot_token
```

### **Configuration Classes**
```python
class Settings(BaseSettings):
    bot_token: str
    admin_id: int
    database_url: str
    # ... other settings
```

## 🛡️ Security Features

### **Middleware Security**
- Rate limiting per user
- Request logging and monitoring
- Input validation and sanitization
- Error handling and user notification

### **Access Control**
- Admin-only decorators
- User authentication
- Subscription validation

## 📊 Monitoring & Logging

### **Logging Levels**
- `INFO` - General operation logs
- `WARNING` - Security events
- `ERROR` - Exception handling
- `DEBUG` - Detailed debugging

### **Log Files**
- `logs/bot.log` - Main application logs
- `logs/nginx/` - Web server logs (production)

## 🔄 Migration Strategy

### **Database Migrations**
```bash
python scripts/migrate.py    # Run migrations
python scripts/db_backup.py # Create backup
```

### **Schema Changes**
1. Update models in `src/models/`
2. Generate migration with Alembic
3. Apply migration with script

## 🧪 Testing Structure

### **Test Organization**
```
tests/
├── unit/                  # Unit tests
├── integration/          # Integration tests
├── e2e/                  # End-to-end tests
└── fixtures/             # Test data
```

### **Test Coverage**
- Model validation
- Service logic
- Handler functionality
- API integrations

## 📈 Scalability Considerations

### **Horizontal Scaling**
- Stateless bot handlers
- Database connection pooling
- Redis for caching (optional)
- Load balancer ready

### **Performance Optimization**
- Async/await throughout
- Database query optimization
- Memory-efficient processing
- Background task scheduling

## 🔮 Future Enhancements

### **Potential Additions**
- Redis caching layer
- Additional payment providers
- Advanced admin features
- Analytics dashboard
- Multi-language support
- Web interface for admins

### **Extension Points**
- New payment methods in `src/services/payment.py`
- Additional protocols in `src/enums/subscription.py`
- Custom middleware in `src/middleware/`
- Utility functions in `utils/`

This structure provides a solid foundation for a scalable, maintainable VPN bot application with clear separation of concerns and comprehensive tooling for development and deployment.
