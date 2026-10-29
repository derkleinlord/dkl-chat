#!/bin/sh
set -eu
backup_dir="${1:-./backups}"
stamp="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir/$stamp"
project_dir="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
config_file="${DKL_BACKUP_CNF:-/etc/dkl-chat/backup.cnf}"
test -r "$config_file" || { echo "Fehlt: $config_file" >&2; exit 1; }
mariadb-dump --defaults-extra-file="$config_file" --single-transaction --routines --triggers --default-character-set=utf8mb4 dklchat | gzip > "$backup_dir/$stamp/database.sql.gz"
tar czf "$backup_dir/$stamp/uploads.tar.gz" -C "$project_dir/backend/uploads" .
echo "Backup gespeichert: $backup_dir/$stamp"

