# Docker Deployment Guide

This guide explains how to deploy the VPN Bot using Docker and Docker Compose.

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- At least 2GB RAM
- 10GB free disk space

## Quick Start

### 1. Clone and Setup
```bash
git clone <repository-url>
cd vpn_bot
cp .env.example .env
```

### 2. Configure Environment
Edit `.env` file with your actual configuration:
```env
BOT_TOKEN=your_actual_bot_token
ADMIN_ID=your_actual_admin_id
SUPPORT_USERNAME=your_support_username
DATABASE_URL=postgresql+asyncpg://vpn_user:vpn_password@postgres:5432/vpn_bot
MARZBAN_URL=https://your-marzban-domain.com
MARZBAN_USERNAME=admin
MARZBAN_PASSWORD=your_marzban_password
CRYPTOBOT_TOKEN=your_cryptobot_token
CRYPTOBOT_PROVIDER_TOKEN=your_cryptobot_provider_token
```

### 3. Start Services
```bash
# For development
make dev

# For production
make prod
```

## Docker Compose Files

### docker-compose.yml (Standard)
Basic setup with PostgreSQL, Redis, and the bot application.

### docker-compose.dev.yml (Development)
Development environment with:
- Hot reload support
- Different ports to avoid conflicts
- Lower prices for testing
- More frequent notifications

### docker-compose.prod.yml (Production)
Production-ready setup with:
- Nginx reverse proxy
- SSL support
- Environment variable configuration
- Optimized for production

## Using Make Commands

### Development Commands
```bash
make dev          # Start development environment
make dev-d        # Start in detached mode
make dev-logs     # View development logs
make dev-shell    # Access development container shell
```

### Production Commands
```bash
make prod         # Start production environment
make prod-logs    # View production logs
make prod-shell   # Access production container shell
```

### Utility Commands
```bash
make build        # Build Docker images
make up           # Start services
make down         # Stop services
make logs         # View logs
make shell        # Access container shell
make clean        # Clean up containers and volumes
make status       # Check service status
make stats        # View resource usage
```

### Database Commands
```bash
make db-shell     # Access PostgreSQL shell
make db-backup    # Create database backup
make backup       # Create backup with timestamp
make restore      # Restore from backup
```

## Environment Variables

### Required Variables
- `BOT_TOKEN` - Telegram bot token
- `ADMIN_ID` - Admin Telegram ID
- `SUPPORT_USERNAME` - Support username without @
- `DATABASE_URL` - PostgreSQL connection string
- `MARZBAN_URL` - Marzban panel URL
- `MARZBAN_USERNAME` - Marzban admin username
- `MARZBAN_PASSWORD` - Marzban admin password
- `CRYPTOBOT_TOKEN` - CryptoBot API token
- `CRYPTOBOT_PROVIDER_TOKEN` - CryptoBot provider token

### Optional Variables
- `SUBSCRIPTION_PRICES` - JSON string with pricing
- `EXPIRY_NOTIFICATION_DAYS` - Comma-separated days for notifications

## Service Architecture

### PostgreSQL Database
- Image: `postgres:15-alpine`
- Port: 5432 (standard), 5433 (development)
- Volume: `postgres_data`
- Health checks enabled

### Redis Cache
- Image: `redis:7-alpine`
- Port: 6379 (standard), 6380 (development)
- Volume: `redis_data`
- Health checks enabled

### VPN Bot Application
- Built from `Dockerfile`
- Port: 8080
- Depends on PostgreSQL and Redis
- Health checks enabled
- Automatic restart

### Nginx (Production Only)
- Image: `nginx:alpine`
- Ports: 80, 443
- SSL support
- Reverse proxy configuration

## Volumes

### Persistent Data
- `postgres_data` - PostgreSQL data
- `redis_data` - Redis data
- `./logs` - Application logs
- `./nginx/ssl` - SSL certificates (production)

## Networking

### Default Network
- Name: `vpn_bot_network`
- Driver: bridge
- All services connected

### Development Network
- Name: `vpn_bot_dev_network`
- Driver: bridge
- Isolated from production

## Health Checks

### PostgreSQL
```bash
pg_isready -U vpn_user -d vpn_bot
```

### Redis
```bash
redis-cli ping
```

### VPN Bot
```python
import asyncio
from bot import bot
asyncio.run(bot.get_me())
```

## SSL Configuration (Production)

### Generate Self-Signed Certificate
```bash
make ssl
```

### Use Let's Encrypt
```bash
# Install certbot
sudo apt-get install certbot

# Generate certificate
sudo certbot certonly --standalone -d your-domain.com

# Copy to nginx/ssl
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/nginx.crt
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/nginx.key
```

## Monitoring

### Check Service Status
```bash
make status
```

### View Resource Usage
```bash
make stats
```

### View Logs
```bash
# All services
make logs

# Specific service
docker-compose logs -f vpn_bot
```

## Backup and Restore

### Create Backup
```bash
make db-backup
# or
make backup
```

### Restore Backup
```bash
make restore
# Follow prompts to select backup file
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check if PostgreSQL is running: `make status`
   - Verify database URL in `.env`
   - Check logs: `make logs`

2. **Bot Token Invalid**
   - Verify `BOT_TOKEN` in `.env`
   - Check bot is running and has correct permissions

3. **Port Conflicts**
   - Development uses ports 5433, 6380, 8080
   - Production uses ports 5432, 6379, 80, 443
   - Check with: `netstat -tulpn | grep LISTEN`

4. **Permission Issues**
   - Ensure Docker daemon is running
   - Check user is in docker group: `groups $USER`

### Debug Mode

Access container shell for debugging:
```bash
make shell  # Production
make dev-shell  # Development
```

### Reset Everything
```bash
make clean-all
```

## Scaling

### Horizontal Scaling
```yaml
# In docker-compose.yml
services:
  vpn_bot:
    deploy:
      replicas: 3
```

### Resource Limits
```yaml
services:
  vpn_bot:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
```

## Security

### Best Practices
1. Use strong passwords for database
2. Enable SSL in production
3. Regularly update base images
4. Use environment variables for secrets
5. Limit container resources
6. Monitor logs for suspicious activity

### Firewall Rules
```bash
# Allow only necessary ports
ufw allow 22    # SSH
ufw allow 80    # HTTP
ufw allow 443   # HTTPS
ufw enable
```

## Updates

### Update Application
```bash
make update
```

### Update Docker Images
```bash
docker-compose pull
docker-compose up -d
```

## Production Deployment Checklist

- [ ] Configure all environment variables
- [ ] Set up SSL certificates
- [ ] Configure firewall rules
- [ ] Set up monitoring
- [ ] Configure backups
- [ ] Test disaster recovery
- [ ] Document deployment process
- [ ] Set up log rotation
- [ ] Configure alerting
