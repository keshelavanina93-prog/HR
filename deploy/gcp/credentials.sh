#!/usr/bin/env bash
# Run in Cloud Shell. Sets a NEW shared beta password and prints it once, together with the
# moderator and demo passwords stored on the server. Use it if you lost the first printout.
#   PROJECT_ID=sivrce-beta-XXXXXX bash deploy/gcp/credentials.sh
# Add ADMIN_EMAIL=you@example.com to change the moderator's login e-mail.
set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID}"
ZONE="${ZONE:-europe-west3-a}"
VM="${VM:-sivrce-beta}"
gcloud config set project "$PROJECT_ID" >/dev/null
gcloud compute ssh "$VM" --zone="$ZONE" --command="sudo env NEW_ADMIN_EMAIL='${ADMIN_EMAIL:-}' bash -s" < "$(dirname "$0")/credentials-vm.sh"
