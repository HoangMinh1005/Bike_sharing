#!/bin/bash
set -e

# Navigate to the repository root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
fi

# Fallback defaults if env variables are empty
DB_USER=${DB_USER:-postgres}
DB_NAME=${DB_NAME:-bike_sharing}

echo "=========================================================="
echo "Initializing Bike Sharing Database: $DB_NAME as user $DB_USER"
echo "=========================================================="

echo "Running 001_create_schemas.sql..."
docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" < sql/init/001_create_schemas.sql

echo "Running 002_create_raw_tables.sql..."
docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" < sql/init/002_create_raw_tables.sql

echo "Running 003_create_staging_tables.sql..."
docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" < sql/init/003_create_staging_tables.sql

echo "Running 005_create_metadata_tables.sql..."
docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" < sql/init/005_create_metadata_tables.sql

echo "Running 006_create_indexes.sql..."
docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" < sql/init/006_create_indexes.sql

echo "=========================================================="
echo "Database schemas and tables initialized successfully!"
echo "=========================================================="
