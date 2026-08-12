#!/bin/bash
# ==============================================================================
# PostgreSQL Backup Script for Bike Sharing Operation Intelligence
# ==============================================================================
# Usage:
#   bash scripts/backup_postgres.sh
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# Load environment variables
if [ -f .env.prod ]; then
    echo "[Backup] Loading environment variables from .env.prod..."
    export $(grep -v '^#' .env.prod | xargs)
elif [ -f .env ]; then
    echo "[Backup] Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
fi

DB_USER=${POSTGRES_USER:-${DB_USER:-postgres}}
DB_NAME=${POSTGRES_DB:-${DB_NAME:-bike_sharing}}
CONTAINER_NAME=${CONTAINER_NAME:-bike_postgres}

# Determine docker compose invocation
if [ -f docker-compose.prod.yml ]; then
    COMPOSE_CMD="docker compose -f docker-compose.prod.yml"
else
    COMPOSE_CMD="docker compose"
fi

# Ensure backups directory exists
BACKUP_DIR="$ROOT_DIR/backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/backup_${DB_NAME}_${TIMESTAMP}.sql"

echo "=========================================================="
echo "Starting PostgreSQL Backup"
echo "Database:  $DB_NAME"
echo "User:      $DB_USER"
echo "Output:    $BACKUP_FILE"
echo "=========================================================="

# Check if postgres container is running
if ! $COMPOSE_CMD ps postgres | grep -q "Up\|running"; then
    echo "[ERROR] PostgreSQL container is not running!"
    echo "Please start the stack first: $COMPOSE_CMD up -d"
    exit 1
fi

# Execute pg_dump inside container
$COMPOSE_CMD exec -T postgres pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists > "$BACKUP_FILE"

if [ -s "$BACKUP_FILE" ]; then
    FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "=========================================================="
    echo "Backup completed successfully!"
    echo "File: $BACKUP_FILE ($FILE_SIZE)"
    echo "=========================================================="
else
    echo "[ERROR] Backup file is empty! Check database status and permissions."
    rm -f "$BACKUP_FILE"
    exit 1
fi
