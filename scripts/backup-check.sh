#!/usr/bin/env bash
# Nightly backup check: run a DB backup and verify it.
# Usage: ./scripts/backup-check.sh [BACKUP_DIR]
# BACKUP_DIR defaults to ./backups; set DATABASE_URL via backend/.env or environment.
# Exit 0 on success, 1 on failure (for cron alerting).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${1:-$REPO_ROOT/backups}"
mkdir -p "$BACKUP_DIR"

# Load backend .env if present
if [ -f "$REPO_ROOT/backend/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$REPO_ROOT/backend/.env" 2>/dev/null || true
  set +a
fi

DATABASE_URL="${DATABASE_URL:-sqlite:///./watch_repair.db}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

if [[ "$DATABASE_URL" == postgresql* ]] || [[ "$DATABASE_URL" == postgres* ]]; then
  # PostgreSQL: use pg_dump (convert postgresql+psycopg to postgres for pg_dump)
  PG_URL="${DATABASE_URL/postgresql+psycopg/postgres}"
  BACKUP_FILE="$BACKUP_DIR/mainspring-$TIMESTAMP.sql.gz"
  if command -v pg_dump >/dev/null 2>&1; then
    pg_dump "$PG_URL" --no-owner --no-acl 2>/dev/null | gzip -c > "$BACKUP_FILE" || { echo "pg_dump failed"; exit 1; }
  else
    echo "pg_dump not found; install PostgreSQL client tools"
    exit 1
  fi
else
  # SQLite
  DB_PATH="$REPO_ROOT/backend/watch_repair.db"
  [ -f "$DB_PATH" ] || DB_PATH="./watch_repair.db"
  [ -f "$DB_PATH" ] || { echo "SQLite DB not found"; exit 1; }
  BACKUP_FILE="$BACKUP_DIR/mainspring-$TIMESTAMP.db"
  cp "$DB_PATH" "$BACKUP_FILE"
fi

# Verify backup exists and has content
if [ ! -f "$BACKUP_FILE" ] || [ ! -s "$BACKUP_FILE" ]; then
  echo "Backup missing or empty: $BACKUP_FILE"
  exit 1
fi
echo "Backup OK: $BACKUP_FILE ($(wc -c < "$BACKUP_FILE") bytes)"
exit 0
