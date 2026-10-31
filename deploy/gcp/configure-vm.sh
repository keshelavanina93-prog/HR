#!/usr/bin/env bash
# Runs ON the VM as root (configure.sh pipes it over SSH). PAIRS holds KEY=base64(value) items.
set -euo pipefail
main(){
  local APP=/opt/sivrce ENVF=/opt/sivrce/deploy/beta/.env pair key val
  [[ -f "$ENVF" ]] || { echo "✗ $ENVF არ არსებობს — ჯერ deploy.sh"; exit 1; }
  for pair in $PAIRS; do
    key="${pair%%=*}"; val="$(printf '%s' "${pair#*=}" | base64 -d)"
    [[ "$key" =~ ^[A-Z_]+$ ]] || { echo "✗ უცნობი გასაღები"; exit 1; }
    # Single quotes keep compose from interpolating '$' and keep spaces intact.
    val="'${val//\'/}'"
    if grep -q "^$key=" "$ENVF"; then
      awk -v k="$key" -v v="$val" 'index($0, k"=")==1 {print k"="v; next} {print}' "$ENVF" > "$ENVF.new"
    else
      { cat "$ENVF"; printf '%s=%s\n' "$key" "$val"; } > "$ENVF.new"
    fi
    chmod 600 "$ENVF.new" && mv "$ENVF.new" "$ENVF"
  done
  cd "$APP"
  local PROFILE=(); grep -q "^SMTP_HOST='\?.\+" "$ENVF" && PROFILE=(--profile mail)
  echo "→ გადატვირთვა"
  docker compose -f deploy/beta/compose.yml --env-file "$ENVF" "${PROFILE[@]}" up -d >/dev/null 2>&1
  sleep 5
  local DC=(docker compose -f deploy/beta/compose.yml --env-file "$ENVF")
  if [[ "$WHAT" == google ]]; then
    "${DC[@]}" exec -T web python -c "
import json,urllib.request
c=json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/auth/google/config',timeout=5))
print('✓ Google შესვლა ჩართულია' if c['enabled'] else '✗ Google შესვლა ჯერ გამორთულია')"
  else
    # Send one real message to the moderator address with the same settings the worker uses.
    "${DC[@]}" exec -T web python -c "
import os,smtplib,ssl
from email.message import EmailMessage
to=os.getenv('ADMIN_EMAIL') or os.environ['SMTP_USER']
m=EmailMessage();m['From']=os.environ['SMTP_FROM'];m['To']=to;m['Subject']='SIVRCE ბეტა — ელფოსტის ტესტი'
m.set_content('ეს სატესტო წერილია. თუ კითხულობ, SIVRCE-ის ბეტა წერილებს აგზავნის.')
try:
  with smtplib.SMTP(os.environ['SMTP_HOST'],int(os.getenv('SMTP_PORT','587')),timeout=20) as s:
    s.starttls(context=ssl.create_default_context());s.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD']);s.send_message(m)
  print('✓ სატესტო წერილი გაიგზავნა: '+to)
except smtplib.SMTPAuthenticationError:print('✗ Google-მა შესვლა უარყო: შეამოწმე App Password და რომ ანგარიშზე ჩართულია 2-ნაბიჯიანი დადასტურება')
except Exception as e:print('✗ გაგზავნა ვერ მოხერხდა: '+type(e).__name__)
" </dev/null
    "${DC[@]}" ps --format '{{.Service}} {{.Status}}' worker </dev/null | sed 's/^/→ /'
  fi
}
main </dev/null
