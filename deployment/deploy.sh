#!/bin/bash
set -Eeuo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte als root ausführen: sudo deployment/deploy.sh" >&2
    exit 1
fi

log_file=/var/log/dkl-chat-deploy.log
exec > >(tee -a "$log_file") 2>&1
trap 'code=$?; echo; echo "FEHLER in Zeile $LINENO: $BASH_COMMAND (Exit-Code $code)"; echo "Vollständiges Protokoll: $log_file"; exit $code' ERR

source_dir="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
install_dir=/var/www/dkl-chat
env_file=/etc/dkl-chat/dkl-chat.env

cleanup() {
    if [ -d "$install_dir/frontend/node_modules" ]; then
        echo "Temporäre Node-Module aufräumen"
        find "$install_dir/frontend/node_modules" -depth -delete
    fi
}
trap cleanup EXIT

for command in rsync python3 node npm nginx systemctl; do
    command -v "$command" >/dev/null 2>&1 || { echo "Fehlendes Programm: $command. Zuerst deployment/install-debian.sh ausführen." >&2; exit 1; }
done
test -f "$env_file" || { echo "Fehlt: $env_file. Zuerst deployment/install-debian.sh ausführen." >&2; exit 1; }

node_major="$(node --version 2>/dev/null | sed 's/^v//' | cut -d. -f1)"
test -n "$node_major" && [ "$node_major" -ge 18 ] || { echo "Node.js 18 oder neuer wird benötigt. Installiert: $(node --version 2>/dev/null || echo unbekannt)" >&2; exit 1; }
free_kb="$(df -Pk "$install_dir" | awk 'NR==2 {print $4}')"
[ "$free_kb" -ge 524288 ] || { echo "Zu wenig freier Speicher. Mindestens 512 MB werden für den Build benötigt." >&2; exit 1; }

echo
echo "=== DKL Chat Deployment $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "Quelle: $source_dir"
echo "Ziel:   $install_dir"
echo "Node:   $(node --version)"

echo "[1/7] Quellcode synchronisieren"
mkdir -p "$install_dir/backend/uploads"
if [ "$source_dir" != "$install_dir" ]; then
    rsync -a --delete \
        --exclude .git \
        --exclude .env \
        --exclude backend/.venv \
        --exclude backend/uploads \
        --exclude frontend/node_modules \
        --exclude frontend/dist \
        "$source_dir/" "$install_dir/"
else
    echo "Quelle und Ziel sind identisch; Synchronisierung wird übersprungen."
fi

echo "[2/7] Python-Umgebung aktualisieren"
test -x "$install_dir/backend/.venv/bin/python" || python3 -m venv "$install_dir/backend/.venv"
"$install_dir/backend/.venv/bin/pip" install --disable-pip-version-check --upgrade pip
"$install_dir/backend/.venv/bin/pip" install --disable-pip-version-check -r "$install_dir/backend/requirements.txt"

echo "[3/7] Frontend-Abhängigkeiten installieren"
(cd "$install_dir/frontend" && npm ci --no-audit --no-fund)

echo "[4/7] Produktions-Frontend bauen"
(cd "$install_dir/frontend" && NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=768}" npm run build)
cleanup

echo "[5/7] Datenbankmigrationen ausführen"
(cd "$install_dir/backend" && set -a && . "$env_file" && set +a && "$install_dir/backend/.venv/bin/alembic" upgrade head)

echo "[6/7] Dienste und Nginx-Konfiguration installieren"
chown -R dkl-chat:dkl-chat "$install_dir/backend/uploads"
install -m 644 "$install_dir/deployment/dkl-chat.service" /etc/systemd/system/dkl-chat.service
if [ -f /etc/letsencrypt/live/chat.dkl.lab.de/fullchain.pem ]; then
    install -m 644 "$install_dir/deployment/dkl-chat.nginx.ssl.conf" /etc/nginx/sites-available/dkl-chat
    public_scheme=https
    echo "HTTPS-Zertifikat erkannt; SSL-Konfiguration aktiviert."
else
    install -m 644 "$install_dir/deployment/dkl-chat.nginx.conf" /etc/nginx/sites-available/dkl-chat
    public_scheme=http
    echo "Noch kein Zertifikat erkannt; HTTP-Konfiguration aktiviert."
fi
ln -sfn /etc/nginx/sites-available/dkl-chat /etc/nginx/sites-enabled/dkl-chat
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl daemon-reload

echo "[7/7] Dienste neu starten"
systemctl enable dkl-chat nginx >/dev/null
systemctl restart dkl-chat
systemctl reload nginx 2>/dev/null || systemctl restart nginx

echo "Deployment erfolgreich."
echo "URLs: ${public_scheme}://chat.dkl.lab.de und ${public_scheme}://chat.dkl.lab.eu"
echo "Status: systemctl status dkl-chat nginx"
echo "Protokoll: $log_file"
