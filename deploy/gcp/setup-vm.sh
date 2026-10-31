#!/usr/bin/env bash
# Runs ON the VM as root (deploy.sh pipes it over SSH). Idempotent.
set -euo pipefail
# Everything sits in main() so bash reads the whole script before any command can consume stdin.
main(){
APP=/opt/sivrce
ENVF="$APP/deploy/beta/.env"

if ! command -v docker >/dev/null; then
  echo "→ Docker-ის დაყენება"
  apt-get update -qq && apt-get install -y -qq ca-certificates curl git openssl >/dev/null
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
  apt-get update -qq && apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin >/dev/null
fi

echo "→ კოდი: $REPO ($BRANCH)"
if [[ -d "$APP/.git" ]]; then git -C "$APP" fetch -q origin "$BRANCH" && git -C "$APP" checkout -q -B "$BRANCH" "origin/$BRANCH"
else git clone -q --branch "$BRANCH" "$REPO" "$APP"; fi

FIRST=0
if [[ ! -f "$ENVF" ]]; then
  FIRST=1
  echo "→ საიდუმლოების გენერაცია (პირველი გაშვება)"
  rnd(){ openssl rand -base64 36 | tr -d '/+=' | cut -c1-"$1"; }
  BETA_PASSWORD="$(rnd 20)"; DEMO_PASSWORD="Demo-$(rnd 14)"; ADMIN_PASSWORD="$(rnd 24)"
  HASH="$(docker run --rm caddy:2 caddy hash-password --plaintext "$BETA_PASSWORD")"
  umask 077
  cat > "$ENVF" <<EOF
BETA_DOMAIN=$DOMAIN
BETA_USER=sivrce
BETA_PASSWORD_HASH='$HASH'
POSTGRES_PASSWORD=$(rnd 32)
DEMO_PASSWORD=$DEMO_PASSWORD
ADMIN_EMAIL=$ADMIN_EMAIL
ADMIN_PASSWORD=$ADMIN_PASSWORD
GOOGLE_CLIENT_ID=
ELEVENLABS_API_KEY=
SMTP_HOST=
SMTP_PORT=587
SMTP_STARTTLS=1
SMTP_FROM=
SMTP_USER=
SMTP_PASSWORD=
BACKUP_BUCKET=$BUCKET
EOF
fi

echo "→ აწყობა და გაშვება"
cd "$APP"
PROFILE=(); grep -q '^SMTP_HOST=.\+' "$ENVF" && PROFILE=(--profile mail)
docker compose -f deploy/beta/compose.yml --env-file "$ENVF" "${PROFILE[@]}" up -d --build --remove-orphans
docker image prune -f >/dev/null

install -m 0755 deploy/beta/backup.sh /usr/local/bin/sivrce-backup
echo "15 3 * * * root /usr/local/bin/sivrce-backup >> /var/log/sivrce-backup.log 2>&1" > /etc/cron.d/sivrce-backup

# Voices: index the starter directory once, then refresh feeds hourly and run queued transcriptions.
DC="docker compose -f $APP/deploy/beta/compose.yml --env-file $ENVF"
cat > /etc/cron.d/sivrce-voices <<EOF
7 * * * * root cd $APP && $DC exec -T web python -m features.voices_cli refresh >> /var/log/sivrce-voices.log 2>&1
*/15 * * * * root cd $APP && $DC exec -T web python -m features.voices_cli transcribe >> /var/log/sivrce-voices.log 2>&1
EOF

echo "→ შემოწმება"
for i in $(seq 1 40); do
  if docker compose -f deploy/beta/compose.yml --env-file "$ENVF" exec -T web python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=3)" </dev/null 2>/dev/null; then OK=1; break; fi
  sleep 3
done
if [[ "${OK:-0}" == 1 ]]; then
  echo "→ Voices: ქართული შოუების ინდექსი"
  docker compose -f deploy/beta/compose.yml --env-file "$ENVF" exec -T web python -m features.voices_cli seed </dev/null 2>&1 | grep -c title | sed 's/^/   შოუ: /'
fi
[[ "${OK:-0}" == 1 ]] && echo "✓ აპლიკაცია მუშაობს" || { echo "✗ აპლიკაცია არ პასუხობს. ლოგები:"; docker compose -f deploy/beta/compose.yml --env-file "$ENVF" logs --tail=60 web migrate; exit 1; }

if [[ $FIRST == 1 ]]; then cat <<EOF

════════════════════════════════════════════════════════════
 შეინახე პაროლების მენეჯერში. ეს მხოლოდ ერთხელ ჩანს.

 საიტი:          https://$DOMAIN
 ბეტას შესვლა:   sivrce / $BETA_PASSWORD
 მოდერატორი:     ${ADMIN_EMAIL:-(ADMIN_EMAIL არ მიუთითე — არ შეიქმნა)} / $ADMIN_PASSWORD
 დემო ანგარიშები: company@ | provider@ | candidate@ | admin@demo.sivrce.ge
                 პაროლი: $DEMO_PASSWORD
════════════════════════════════════════════════════════════
EOF
fi
}
main </dev/null
