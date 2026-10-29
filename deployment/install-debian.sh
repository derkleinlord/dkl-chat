#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte als root ausführen: sudo deployment/install-debian.sh" >&2
    exit 1
fi

project_dir="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
install_dir=/var/www/dkl-chat

apt-get update
apt-get install -y --no-install-recommends mariadb-server mariadb-client nginx certbot python3-certbot-nginx python3 python3-venv python3-pip nodejs npm rsync ca-certificates

id dkl-chat >/dev/null 2>&1 || useradd --system --home-dir "$install_dir" --shell /usr/sbin/nologin dkl-chat
mkdir -p "$install_dir" /etc/dkl-chat
rsync -a --delete --exclude .git --exclude .env --exclude backend/.venv --exclude backend/uploads --exclude frontend/node_modules --exclude frontend/dist "$project_dir/" "$install_dir/"
mkdir -p "$install_dir/backend/uploads"

if [ ! -f /etc/dkl-chat/dkl-chat.env ]; then
    install -m 600 "$project_dir/.env.example" /etc/dkl-chat/dkl-chat.env
    echo "Konfiguration angelegt: /etc/dkl-chat/dkl-chat.env"
    echo "Bitte Kennwörter, SECRET_KEY, Domain und Einladungscodes anpassen und das Skript erneut starten."
    exit 2
fi

db_password="$(sed -n 's#^DATABASE_URL=mysql+pymysql://dklchat:\([^@]*\)@.*#\1#p' /etc/dkl-chat/dkl-chat.env)"
test -n "$db_password" && test "$db_password" != "change-me-long-random" || { echo "Bitte zuerst ein sicheres Datenbankkennwort in /etc/dkl-chat/dkl-chat.env setzen." >&2; exit 2; }
case "$db_password" in *[!A-Za-z0-9_.-]*) echo "Das Datenbankkennwort darf nur Buchstaben, Zahlen, Punkt, Unterstrich und Bindestrich enthalten." >&2; exit 2;; esac

mariadb <<SQL
CREATE DATABASE IF NOT EXISTS dklchat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'dklchat'@'127.0.0.1' IDENTIFIED BY '${db_password}';
ALTER USER 'dklchat'@'127.0.0.1' IDENTIFIED BY '${db_password}';
GRANT ALL PRIVILEGES ON dklchat.* TO 'dklchat'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL

cat > /etc/dkl-chat/backup.cnf <<EOF
[client]
user=dklchat
password=${db_password}
host=127.0.0.1
default-character-set=utf8mb4
EOF
chmod 600 /etc/dkl-chat/backup.cnf /etc/dkl-chat/dkl-chat.env

systemctl enable --now mariadb
"$project_dir/deployment/deploy.sh"
echo "DKL Chat ist installiert. Status: systemctl status dkl-chat nginx mariadb"
