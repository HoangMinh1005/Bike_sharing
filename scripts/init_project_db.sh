#!/bin/bash
set -e

# Navigate to the repository root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Load environment variables from .env.prod or .env file if it exists
if [ -f .env.prod ]; then
    echo "Loading environment variables from .env.prod..."
    export $(grep -v '^#' .env.prod | xargs)
elif [ -f .env ]; then
    echo "Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
fi

# Determine compose file
if [ -f docker-compose.prod.yml ]; then
    COMPOSE_CMD="docker compose -f docker-compose.prod.yml"
else
    COMPOSE_CMD="docker compose"
fi

# Fallback defaults if env variables are empty
DB_USER=${POSTGRES_USER:-${DB_USER:-postgres}}
DB_NAME=${POSTGRES_DB:-${DB_NAME:-bike_sharing}}

echo "=========================================================="
echo "Initializing Bike Sharing Database: $DB_NAME as user $DB_USER"
echo "=========================================================="

echo "Running 001_create_schemas.sql..."
$COMPOSE_CMD exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" < sql/init/001_create_schemas.sql

echo "Running 002_create_raw_tables.sql..."
$COMPOSE_CMD exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" < sql/init/002_create_raw_tables.sql

echo "Running 003_create_staging_tables.sql..."
$COMPOSE_CMD exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" < sql/init/003_create_staging_tables.sql

echo "Running 004_create_mart_tables.sql..."
$COMPOSE_CMD exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" < sql/init/004_create_mart_tables.sql

echo "Running 005_create_metadata_tables.sql..."
$COMPOSE_CMD exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" < sql/init/005_create_metadata_tables.sql

echo "Running 006_create_indexes.sql..."
$COMPOSE_CMD exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" < sql/init/006_create_indexes.sql

echo "=========================================================="
echo "Database schemas and tables initialized successfully!"
echo "=========================================================="
