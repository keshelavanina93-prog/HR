#!/usr/bin/env bash
# Run in Google Cloud Shell (https://shell.cloud.google.com), from a clone of this repository:
#   bash deploy/gcp/provision.sh
# Creates a NEW Google Cloud project for the SIVRCE closed beta, links it to your billing account
# (where startup credits are applied), and creates one VM, a static IP, a firewall rule and a
# private backup bucket. Safe to re-run: existing resources are kept.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sivrce-beta-$(date +%y%m%d)}"
REGION="${REGION:-europe-west3}"          # Frankfurt
ZONE="${ZONE:-${REGION}-a}"
VM="${VM:-sivrce-beta}"
MACHINE="${MACHINE:-e2-medium}"           # 2 vCPU, 4 GB — enough for app, PostgreSQL and ClamAV
DOMAIN="${DOMAIN:-beta.ncore.space}"

say(){ printf '\n\033[1m%s\033[0m\n' "$*"; }

say "1/6 პროექტი: $PROJECT_ID"
if ! gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud projects create "$PROJECT_ID" --name="SIVRCE Beta"
fi
gcloud config set project "$PROJECT_ID" >/dev/null

say "2/6 ბილინგი (კრედიტები ბილინგის ანგარიშზეა)"
if [[ "$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingEnabled)')" != "True" ]]; then
  BILLING="${BILLING_ACCOUNT:-}"
  if [[ -z "$BILLING" ]]; then
    gcloud billing accounts list --filter=open=true --format='table(name,displayName)'
    mapfile -t ACCOUNTS < <(gcloud billing accounts list --filter=open=true --format='value(name)')
    if [[ ${#ACCOUNTS[@]} -eq 1 ]]; then BILLING="${ACCOUNTS[0]}"
    else read -rp "რომელ ბილინგის ანგარიშზე მივაბა? (ზემოთ NAME სვეტიდან): " BILLING; fi
  fi
  gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING"
fi

say "3/6 სერვისების ჩართვა"
gcloud services enable compute.googleapis.com storage.googleapis.com

say "4/6 მუდმივი IP და firewall"
gcloud compute addresses describe "$VM-ip" --region="$REGION" >/dev/null 2>&1 \
  || gcloud compute addresses create "$VM-ip" --region="$REGION"
IP="$(gcloud compute addresses describe "$VM-ip" --region="$REGION" --format='value(address)')"
gcloud compute firewall-rules describe sivrce-web >/dev/null 2>&1 \
  || gcloud compute firewall-rules create sivrce-web --allow=tcp:80,tcp:443,udp:443 --target-tags=sivrce-web

say "5/6 სარეზერვო ასლების საცავი (30 დღე)"
BUCKET="gs://${PROJECT_ID}-backups"
if ! gcloud storage buckets describe "$BUCKET" >/dev/null 2>&1; then
  gcloud storage buckets create "$BUCKET" --location="$REGION" --uniform-bucket-level-access --public-access-prevention
  printf '{"rule":[{"action":{"type":"Delete"},"condition":{"age":30}}]}' > /tmp/sivrce-lifecycle.json
  gcloud storage buckets update "$BUCKET" --lifecycle-file=/tmp/sivrce-lifecycle.json
fi

say "6/6 სერვერი $VM ($MACHINE, $ZONE)"
if ! gcloud compute instances describe "$VM" --zone="$ZONE" >/dev/null 2>&1; then
  gcloud compute instances create "$VM" --zone="$ZONE" --machine-type="$MACHINE" \
    --image-family=debian-12 --image-project=debian-cloud --boot-disk-size=40GB --boot-disk-type=pd-balanced \
    --address="$IP" --tags=sivrce-web --scopes=storage-rw,logging-write,monitoring-write \
    --metadata=enable-oslogin=TRUE
fi

cat <<EOF

────────────────────────────────────────────────────────
მზადაა. ახლა DNS:

  ტიპი: A   სახელი: ${DOMAIN%%.*}   მნიშვნელობა: $IP   TTL: 300

  (თუ Cloudflare-ს იყენებ, ჩანაწერი დატოვე „DNS only“ — ნაცრისფერი ღრუბელი.)

შემდეგ გაუშვი:
  PROJECT_ID=$PROJECT_ID ADMIN_EMAIL=შენი@ელფოსტა bash deploy/gcp/deploy.sh
────────────────────────────────────────────────────────
EOF
