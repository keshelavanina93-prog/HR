#!/usr/bin/env bash
# Run in Google Cloud Shell after provision.sh and after the DNS record exists:
#   PROJECT_ID=sivrce-beta-XXXXXX ADMIN_EMAIL=you@example.com bash deploy/gcp/deploy.sh
# Re-run any time to deploy the latest code from BRANCH. Secrets are generated on the
# server on first run and printed ONCE in this terminal — store them in a password manager.
set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID (printed by provision.sh)}"
ZONE="${ZONE:-europe-west3-a}"
VM="${VM:-sivrce-beta}"
DOMAIN="${DOMAIN:-beta.ncore.space}"
BRANCH="${BRANCH:-main}"
REPO="${REPO:-https://github.com/keshelavanina93-prog/HR.git}"
ADMIN_EMAIL="${ADMIN_EMAIL:-}"
BUCKET="gs://${PROJECT_ID}-backups"

gcloud config set project "$PROJECT_ID" >/dev/null
IP="$(gcloud compute instances describe "$VM" --zone="$ZONE" --format='value(networkInterfaces[0].accessConfigs[0].natIP)')"
RESOLVED="$(getent hosts "$DOMAIN" | awk '{print $1}' | head -1 || true)"
if [[ "$RESOLVED" != "$IP" ]]; then
  echo "⚠ $DOMAIN ჯერ არ მიუთითებს $IP-ზე (ახლა: ${RESOLVED:-არაფერი}). HTTPS სერტიფიკატი DNS-ის გავრცელების შემდეგ აიღება."
fi

gcloud compute ssh "$VM" --zone="$ZONE" --command="sudo env DOMAIN='$DOMAIN' BRANCH='$BRANCH' REPO='$REPO' ADMIN_EMAIL='$ADMIN_EMAIL' BUCKET='$BUCKET' bash -s" < "$(dirname "$0")/setup-vm.sh"
