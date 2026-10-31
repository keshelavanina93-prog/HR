#!/usr/bin/env bash
# Run in Cloud Shell. Turns on optional beta features and tests them right away.
#   PROJECT_ID=sivrce-beta-XXXXXX bash deploy/gcp/configure.sh google   # Google sign-in (asks for the Web client ID)
#   PROJECT_ID=sivrce-beta-XXXXXX bash deploy/gcp/configure.sh mail     # e-mail via Google Workspace SMTP (asks for an App Password)
# Values are typed here (the password hidden), sent to the server over SSH and stored only in
# /opt/sivrce/deploy/beta/.env. Nothing is written to the repository.
set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID}"
ZONE="${ZONE:-europe-west3-a}"
VM="${VM:-sivrce-beta}"
WHAT="${1:-}"
b64(){ printf '%s' "$1" | base64 -w0; }

case "$WHAT" in
  google)
    read -rp "Google OAuth Web client ID (….apps.googleusercontent.com): " CID
    [[ "$CID" =~ ^[0-9]+-[a-z0-9]+\.apps\.googleusercontent\.com$ ]] || { echo "✗ ეს არ ჰგავს Web client ID-ს"; exit 1; }
    PAIRS="GOOGLE_CLIENT_ID=$(b64 "$CID")"
    ;;
  mail)
    read -rp "გამგზავნი ანგარიში [connect@nyxcore.space]: " USER; USER="${USER:-connect@nyxcore.space}"
    read -rsp "App Password (16 ასო; Google აჩვენებს ჰარებით — ჰარები არ აქვს მნიშვნელობა): " PASS; echo
    PASS="${PASS// /}"
    [[ ${#PASS} -eq 16 ]] || { echo "✗ App Password 16 სიმბოლო უნდა იყოს"; exit 1; }
    read -rp "გამგზავნის სახელი [SIVRCE]: " NAME; NAME="${NAME:-SIVRCE}"
    PAIRS="SMTP_HOST=$(b64 smtp.gmail.com) SMTP_PORT=$(b64 587) SMTP_STARTTLS=$(b64 1) SMTP_USER=$(b64 "$USER") SMTP_PASSWORD=$(b64 "$PASS") SMTP_FROM=$(b64 "$NAME <$USER>")"
    ;;
  *) echo "გამოყენება: configure.sh google | mail"; exit 1 ;;
esac

gcloud config set project "$PROJECT_ID" >/dev/null
gcloud compute ssh "$VM" --zone="$ZONE" --command="sudo env WHAT='$WHAT' PAIRS='$PAIRS' bash -s" < "$(dirname "$0")/configure-vm.sh"
