#!/bin/sh
set -eu
source_dir="${1:?Aufruf: scripts/restore.sh PFAD_ZUM_BACKUP}"
test -f "$source_dir/database.sql.gz" && test -f "$source_dir/uploads.tar.gz"
project_dir="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
config_file="${DKL_BACKUP_CNF:-/etc/dkl-chat/backup.cnf}"
test -r "$config_file" || { echo "Fehlt: $config_file" >&2; exit 1; }
printf 'Bestehende DKL-Chat-Daten werden ersetzt. RESTORE eingeben: '
read -r confirmation
test "$confirmation" = "RESTORE" || { echo "Abgebrochen."; exit 1; }
systemctl stop dkl-chat
gzip -dc "$source_dir/database.sql.gz" | mariadb --defaults-extra-file="$config_file" dklchat
find "$project_dir/backend/uploads" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
tar xzf "$source_dir/uploads.tar.gz" -C "$project_dir/backend/uploads"
chown -R dkl-chat:dkl-chat "$project_dir/backend/uploads"
systemctl start dkl-chat
echo "Wiederherstellung abgeschlossen."

