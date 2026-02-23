#!/bin/bash
set -e

# Wait for database to be ready
echo "Waiting for PostgreSQL..."
while ! nc -z postgres 5432; do
  sleep 0.1
done
echo "PostgreSQL is ready!"

# Wait for Redis to be ready (if used)
echo "Waiting for Redis..."
while ! nc -z redis 6379; do
  sleep 0.1
done
echo "Redis is ready!"

# Run database migrations/initialization
echo "Initializing database..."
python setup.py

# Start the application
echo "Starting VPN Bot..."
exec "$@"
