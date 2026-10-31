#!/usr/bin/env bash
# Nightly backup: PostgreSQL dump + uploaded photos and CVs → private Cloud Storage bucket.
# Installed by setup-vm.sh as /usr/local/bin/sivrce-backup (cron 03:15 UTC). Bucket deletes objects after 30 days.
set -euo pipefail
APP=/opt/sivrce
ENVF="$APP/deploy/beta/.env"
BUCKET="$(grep '^BACKUP_BUCKET=' "$ENVF" | cut -d= -f2-)"
[[ -n "$BUCKET" ]] || { echo "BACKUP_BUCKET not set"; exit 1; }
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
cd "$APP"
docker compose -f deploy/beta/compose.yml --env-file "$ENVF" exec -T database pg_dump -U sivrce -d sivrce -Fc > "$TMP/sivrce.dump"
for vol in documents media; do
  docker run --rm -v "sivrce-beta_${vol}:/data:ro" -v "$TMP:/out" alpine tar -czf "/out/${vol}.tar.gz" -C /data .
done
gcloud storage cp "$TMP"/* "$BUCKET/$STAMP/" --quiet
echo "$STAMP backup ok"
