#!/bin/bash
# ==============================================================================
# PostgreSQL Restore Script for Bike Sharing Operation Intelligence
# ==============================================================================
# Usage:
#   bash scripts/restore_postgres.sh <backup_file_path>
#
# Example:
#   bash scripts/restore_postgres.sh backups/backup_bike_sharing_20260811_120000.sql
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

if [ -z "$1" ]; then
    echo "=========================================================="
    echo "PostgreSQL Restore Tool"
    echo "=========================================================="
    echo "Error: Missing backup file argument."
    echo ""
    echo "Usage:"
    echo "  bash scripts/restore_postgres.sh <backup_file_path>"
    echo ""
    echo "Example:"
    echo "  bash scripts/restore_postgres.sh backups/backup_bike_sharing_20260811_120000.sql"
    echo "=========================================================="
    exit 1
fi

BACKUP_FILE="$1"

# Resolve relative path if needed
if [[ "$BACKUP_FILE" != /* ]]; then
    BACKUP_FILE="$ROOT_DIR/$BACKUP_FILE"
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "[ERROR] Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Load environment variables
if [ -f .env.prod ]; then
    echo "[Restore] Loading environment variables from .env.prod..."
    export $(grep -v '^#' .env.prod | xargs)
elif [ -f .env ]; then
    echo "[Restore] Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
fi

DB_USER=${POSTGRES_USER:-${DB_USER:-postgres}}
DB_NAME=${POSTGRES_DB:-${DB_NAME:-bike_sharing}}

# Determine docker compose invocation
if [ -f docker-compose.prod.yml ]; then
    COMPOSE_CMD="docker compose -f docker-compose.prod.yml"
else
    COMPOSE_CMD="docker compose"
fi

echo "=========================================================="
echo "Starting PostgreSQL Restore"
echo "Target DB:  $DB_NAME"
echo "User:       $DB_USER"
echo "Source:     $BACKUP_FILE"
echo "=========================================================="

# Check if postgres container is running
if ! $COMPOSE_CMD ps postgres | grep -q "Up\|running"; then
    echo "[ERROR] PostgreSQL container is not running!"
    echo "Please start the stack first: $COMPOSE_CMD up -d"
    exit 1
fi

# Execute restore via psql
$COMPOSE_CMD exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" < "$BACKUP_FILE"

echo "=========================================================="
echo "Database restored successfully from: $BACKUP_FILE"
echo "=========================================================="
