#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SEED_DEMO=1 APP_ENV=development COOKIE_SECURE=0 DATABASE_URL=sqlite:///./sivrce.db
echo 'Open http://127.0.0.1:8000 in your browser'
python -m uvicorn server:app --host 127.0.0.1 --port 8000
