#!/usr/bin/env bash
# Runs ON the VM as root (credentials.sh pipes it over SSH).
set -euo pipefail
main(){
  local ENVF=/opt/sivrce/deploy/beta/.env
  [[ -f "$ENVF" ]] || { echo "✗ $ENVF არ არსებობს — ჯერ deploy.sh"; exit 1; }
  local PASS HASH
  PASS="$(openssl rand -base64 36 | tr -d '/+=' | cut -c1-20)"
  HASH="$(docker run --rm caddy:2 caddy hash-password --plaintext "$PASS")"
  # bcrypt hashes contain '$' and '/', so rewrite the line with awk instead of sed.
  awk -v h="$HASH" 'BEGIN{FS=OFS="="} /^BETA_PASSWORD_HASH=/{print "BETA_PASSWORD_HASH='\''" h "'\''"; next} {print}' "$ENVF" > "$ENVF.new"
  chmod 600 "$ENVF.new" && mv "$ENVF.new" "$ENVF"
  cd /opt/sivrce
  docker compose -f deploy/beta/compose.yml --env-file "$ENVF" up -d --force-recreate caddy >/dev/null 2>&1
  # Optionally move the moderator account to a new login e-mail.
  local NEW="${NEW_ADMIN_EMAIL:-}" OLD
  OLD="$(grep '^ADMIN_EMAIL=' "$ENVF" | cut -d= -f2-)"
  if [[ -n "$NEW" && "$NEW" != "$OLD" ]]; then
    NEW="$(printf '%s' "$NEW" | tr '[:upper:]' '[:lower:]')"
    [[ "$NEW" == ?*@?*.?* && "$NEW" != *[[:space:]\'\"]* ]] || { echo "✗ ელფოსტა არასწორია: $NEW"; exit 1; }
    docker compose -f deploy/beta/compose.yml --env-file "$ENVF" exec -T database \
      psql -U sivrce -d sivrce -v ON_ERROR_STOP=1 -v old="$OLD" -v new="$NEW" >/dev/null \
      <<< "UPDATE users SET email = :'new' WHERE email = :'old' AND admin;"
    awk -v e="$NEW" 'BEGIN{FS=OFS="="} /^ADMIN_EMAIL=/{print "ADMIN_EMAIL=" e; next} {print}' "$ENVF" > "$ENVF.new"
    chmod 600 "$ENVF.new" && mv "$ENVF.new" "$ENVF"
    echo "✓ მოდერატორის ელფოსტა შეიცვალა"
  fi
  local DOMAIN ADMIN_EMAIL ADMIN_PASSWORD DEMO_PASSWORD
  DOMAIN="$(grep '^BETA_DOMAIN=' "$ENVF" | cut -d= -f2-)"
  ADMIN_EMAIL="$(grep '^ADMIN_EMAIL=' "$ENVF" | cut -d= -f2-)"
  ADMIN_PASSWORD="$(grep '^ADMIN_PASSWORD=' "$ENVF" | cut -d= -f2-)"
  DEMO_PASSWORD="$(grep '^DEMO_PASSWORD=' "$ENVF" | cut -d= -f2-)"
  cat <<EOF

════════════════════════════════════════════════════════════
 შეინახე პაროლების მენეჯერში. ეს მხოლოდ ერთხელ ჩანს.

 საიტი:          https://$DOMAIN
 ბეტას შესვლა:   sivrce / $PASS        (ახალი; ძველი აღარ მუშაობს)
 მოდერატორი:     ${ADMIN_EMAIL:-(არ არის მითითებული)} / $ADMIN_PASSWORD
 დემო ანგარიშები: company@ | provider@ | candidate@ | admin@demo.sivrce.ge
                 პაროლი: $DEMO_PASSWORD
════════════════════════════════════════════════════════════
EOF
}
main </dev/null
