.PHONY: help build up down logs shell clean prod dev test migrate setup migrate-prod migrate-down migration-current migration-history migration-new migration-autogenerate

# Default target
help:
	@echo "Available commands:"
	@echo "  build              - Build Docker images"
	@echo "  up                 - Start services"
	@echo "  down               - Stop services"
	@echo "  logs               - Show logs"
	@echo "  shell              - Access bot shell"
	@echo "  clean              - Clean up containers and volumes"
	@echo "  prod               - Production deployment"
	@echo "  dev                - Development deployment"
	@echo "  test               - Run tests"
	@echo "  migrate            - Run database migrations"
	@echo "  migrate-prod        - Run production migrations"
	@echo "  migrate-down        - Downgrade migration (REVISION=<rev>)"
	@echo "  migration-current   - Show current migration"
	@echo "  migration-history   - Show migration history"
	@echo "  migration-new       - Create new migration (MESSAGE=<msg>)"
	@echo "  migration-autogenerate - Create autogenerate migration"
	@echo "  setup              - Initial setup"

# Development commands
dev:
	docker-compose -f docker-compose.dev.yml up --build

dev-d:
	docker-compose -f docker-compose.dev.yml up -d --build

dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f vpn_bot

dev-shell:
	docker-compose -f docker-compose.dev.yml exec vpn_bot bash

# Production commands
prod:
	docker-compose -f docker-compose.prod.yml up --build -d

prod-logs:
	docker-compose -f docker-compose.prod.yml logs -f vpn_bot

prod-shell:
	docker-compose -f docker-compose.prod.yml exec vpn_bot bash

# Standard commands
build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

shell:
	docker-compose exec vpn_bot bash

# Database commands
db-shell:
	docker-compose exec postgres psql -U vpn_user -d vpn_bot

db-backup:
	docker-compose exec postgres pg_dump -U vpn_user vpn_bot > backup_$(shell date +%Y%m%d_%H%M%S).sql

# Utility commands
clean:
	docker-compose down -v
	docker system prune -f

clean-all:
	docker-compose down -v --rmi all
	docker system prune -af

test:
	docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

setup:
	@echo "Setting up VPN Bot..."
	@echo "1. Copy .env.example to .env and configure your settings"
	@echo "2. Run 'make dev' to start development environment"
	@echo "3. Run 'make prod' to start production environment"

# Monitoring
status:
	docker-compose ps

stats:
	docker stats

# SSL certificates (for production)
ssl:
	@echo "Generating SSL certificates..."
	mkdir -p nginx/ssl
	openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
		-keyout nginx/ssl/nginx.key \
		-out nginx/ssl/nginx.crt \
		-subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

# Update commands
update:
	docker-compose pull
	docker-compose up -d --build

# Backup and restore
backup:
	@echo "Creating backup..."
	docker-compose exec postgres pg_dump -U vpn_user vpn_bot > backup_$(shell date +%Y%m%d_%H%M%S).sql

restore:
	@echo "Restoring from backup..."
	@read -p "Enter backup file: " backup_file; \
	docker-compose exec -T postgres psql -U vpn_user vpn_bot < $$backup_file

# Database migration
migrate:
	@echo "Running database migration..."
	docker-compose -f docker-compose.dev.yml exec vpn_bot python scripts/alembic_manager.py upgrade

migrate-prod:
	@echo "Running production database migration..."
	docker-compose exec vpn_bot python scripts/alembic_manager.py upgrade

migrate-down:
	@echo "Downgrading database migration..."
	@if [ -z "$(REVISION)" ]; then \
		echo "❌ REVISION environment variable required"; \
		echo "Usage: make migrate-down REVISION=<revision>"; \
		exit 1; \
	fi
	docker-compose -f docker-compose.dev.yml exec vpn_bot python scripts/alembic_manager.py downgrade $(REVISION)

migration-current:
	@echo "Showing current migration..."
	docker-compose -f docker-compose.dev.yml exec vpn_bot python scripts/alembic_manager.py current

migration-history:
	@echo "Showing migration history..."
	docker-compose -f docker-compose.dev.yml exec vpn_bot python scripts/alembic_manager.py history

migration-new:
	@echo "Creating new migration..."
	@if [ -z "$(MESSAGE)" ]; then \
		docker-compose -f docker-compose.dev.yml exec vpn_bot python scripts/alembic_manager.py revision; \
	else \
		docker-compose -f docker-compose.dev.yml exec vpn_bot python scripts/alembic_manager.py revision "$(MESSAGE)"; \
	fi

migration-autogenerate:
	@echo "Creating autogenerate migration..."
	@if [ -z "$(MESSAGE)" ]; then \
		docker-compose -f docker-compose.dev.yml exec vpn_bot python scripts/alembic_manager.py autogenerate; \
	else \
		docker-compose -f docker-compose.dev.yml exec vpn_bot python scripts/alembic_manager.py autogenerate "$(MESSAGE)"; \
	fi
