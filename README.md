# DKL Chat

DKL Chat ist ein selbst gehosteter Retro-Messenger im Stil der Jahre 2005–2008. Das MVP kombiniert eine klassische Kontaktliste und frei verschiebbare Einzelfenster mit React, FastAPI und MariaDB.

Es wird **kein Docker** verwendet. Die Anwendung läuft nativ auf einer Debian-VM mit systemd und Nginx.

## Enthaltenes MVP

- Einladungspflicht, Argon2id-Passwort-Hashes und dauerhafte achtstellige DKL-Nummern
- HttpOnly-Sitzungscookie, CSRF-Schutz und Rate-Limits
- Kontaktanfragen per DKL-Nummer, Annahme/Ablehnung und Kontaktliste
- Live-Status Online, Abwesend, Beschäftigt und Unsichtbar
- Persistenter 1:1-Verlauf und Echtzeit-Zustellung über authentifizierte WebSockets
- Mehrere verschiebbare, minimierbare und maximierbare Chatfenster
- Anstupsen, Schreibindikator, Retro-Taskleiste und mobile Darstellung
- MariaDB, Alembic-Migrationen, Nginx, systemd, Healthcheck, Backup und Restore

Dateiversand, Profilbilder, Nachrichtenbearbeitung, Kontaktgruppen per Drag-and-drop und Gruppenchats sind spätere Ausbaustufen.

## Empfohlenes System

- Debian 12 oder 13 in einer Proxmox-VM
- 2 vCPU
- 2 GB RAM
- 20 GB Speicher
- DNS-Eintrag für die spätere HTTPS-Domain

MariaDB wird verwendet, weil es auf Debian direkt gepflegt wird, wenig Ressourcen benötigt und vollständig mit dem benötigten MySQL-Protokoll kompatibel ist.

## Native Installation auf Debian

Repository zunächst in ein Arbeitsverzeichnis kopieren. Danach:

```sh
sudo chmod +x deployment/install-debian.sh scripts/*.sh
sudo deployment/install-debian.sh
```

Beim ersten Lauf legt das Skript `/etc/dkl-chat/dkl-chat.env` an und beendet sich. Dort anschließend konfigurieren:

```dotenv
DATABASE_URL=mysql+pymysql://dklchat:EIN_LANGES_ZUFAELLIGES_PASSWORT@127.0.0.1:3306/dklchat?charset=utf8mb4
SECRET_KEY=EIN_MINDESTENS_32_BYTE_LANGER_ZUFAELLIGER_SCHLUESSEL
INVITE_CODES=CODE-FUER-ANNA,CODE-FUER-BEN
COOKIE_SECURE=false
ALLOWED_ORIGINS=https://chat.dkl.lab.de,https://chat.dkl.lab.eu
```

Für das Datenbankkennwort nur Buchstaben, Zahlen, Punkt, Unterstrich und Bindestrich verwenden. Danach erneut ausführen:

```sh
sudo deployment/install-debian.sh
```

Das Skript installiert MariaDB, Python, Node.js und Nginx, erstellt Benutzer und Datenbank, baut das Frontend, führt Alembic aus und startet alle Dienste.

Status prüfen:

```sh
systemctl status dkl-chat mariadb nginx
curl http://127.0.0.1/api/health
journalctl -u dkl-chat -f
```

## Deployment und HTTPS

Für jede neue Version genügt anschließend:

```sh
sudo deployment/deploy.sh
```

Das Projekt liegt auf dem Server unter `/var/www/dkl-chat`. Das Skript aktualisiert dort das Python-venv, installiert die exakt gesperrten npm-Abhängigkeiten, baut das Frontend, entfernt anschließend die nur zum Build benötigten Node-Module, führt Alembic-Migrationen aus, prüft Nginx und startet die Dienste neu. Wird es aus einem anderen Checkout gestartet, synchronisiert es diesen zuerst nach `/var/www/dkl-chat`. Datenbank und Uploads werden nicht überschrieben.

Jeder Lauf schreibt zusätzlich nach `/var/log/dkl-chat-deploy.log`. Bei einem Fehler zeigt das Skript die betroffene Zeile, den fehlgeschlagenen Befehl und den Exit-Code an. Das aktuelle Protokoll lässt sich so anzeigen:

```sh
sudo tail -n 100 /var/log/dkl-chat-deploy.log
```

Beide DNS-Namen müssen auf die VM zeigen. Beim ersten Deployment läuft Nginx zunächst über HTTP, damit das gemeinsame Zertifikat beantragt werden kann:

```sh
sudo certbot --nginx \
  -d chat.dkl.lab.de \
  -d chat.dkl.lab.eu
sudo deployment/deploy.sh
```

Der zweite Deploy erkennt das Zertifikat automatisch, aktiviert die mitgelieferte HTTPS-Konfiguration und leitet HTTP dauerhaft auf HTTPS um. In `/etc/dkl-chat/dkl-chat.env` muss stehen:

```dotenv
COOKIE_SECURE=true
ALLOWED_ORIGINS=https://chat.example.de
```

Anschließend `sudo systemctl restart dkl-chat` ausführen. Port 8000 bleibt ausschließlich an `127.0.0.1` gebunden.

## Lokale Entwicklung

```sh
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL='mysql+pymysql://dklchat:PASSWORT@127.0.0.1:3306/dklchat?charset=utf8mb4'
uvicorn app.main:app --reload
```

Frontend in einem zweiten Terminal:

```sh
cd frontend
npm install
npm run dev
```

Die automatisierten Backend-Tests verwenden eine isolierte SQLite-Testdatenbank. Der Serverbetrieb verwendet ausschließlich MariaDB.

## Tests

```sh
cd backend && pytest -q
cd frontend && npm run build
```

## Backup und Wiederherstellung

Das Installationsskript erzeugt `/etc/dkl-chat/backup.cnf` mit restriktiven Dateirechten. Backup erstellen:

```sh
sudo ./scripts/backup.sh /var/backups/dkl-chat
```

Gesichert werden ein konsistenter MariaDB-Dump und das Upload-Verzeichnis. Das Restore ersetzt die vorhandenen Daten und verlangt deshalb ausdrücklich die Eingabe `RESTORE`:

```sh
sudo ./scripts/restore.sh /var/backups/dkl-chat/20261029-180000
```

## Wichtige Pfade

- Anwendung: `/var/www/dkl-chat`
- Konfiguration: `/etc/dkl-chat/dkl-chat.env`
- Backup-Zugang: `/etc/dkl-chat/backup.cnf`
- systemd-Dienst: `/etc/systemd/system/dkl-chat.service`
- Nginx-Konfiguration: `/etc/nginx/sites-available/dkl-chat`
- Logs: `journalctl -u dkl-chat`

## Sicherheitsbetrieb

- Einen zufälligen `SECRET_KEY` und getrennte, einmalige Einladungscodes verwenden.
- MariaDB nur lokal binden und Port 3306 nicht in der Firewall öffnen.
- Nur HTTPS veröffentlichen und `COOKIE_SECURE=true` setzen.
- Debian regelmäßig aktualisieren und verschlüsselte Backups testen.
- Bei mehreren Backend-Instanzen Präsenz, WebSocket-Fan-out und Rate-Limits auf Redis oder einen vergleichbaren gemeinsamen Dienst umstellen. Das MVP ist für eine Backend-Instanz ausgelegt.
