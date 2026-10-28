# SIVRCE / Human Potential Index — 2026 Product Beta

[![Tests](https://github.com/keshelavanina93-prog/HR/actions/workflows/tests.yml/badge.svg)](https://github.com/keshelavanina93-prog/HR/actions/workflows/tests.yml)

Source repository: [keshelavanina93-prog/HR](https://github.com/keshelavanina93-prog/HR). For developer setup, checks and pull requests, see [CONTRIBUTING.md](CONTRIBUTING.md). Local databases, private uploads, credentials and virtual environments are excluded from Git. The local launchers generate demonstration data on first run.

**Not an HTML mockup.** This package contains a FastAPI/SQLAlchemy multi-user application, a server-rendered editorial frontend with vanilla JavaScript interactions, persistent relational storage, protected CV files and tested business workflows. It is **not ready to take live payments or collect real candidate CVs publicly**.

## Windows — run locally

1. Install Python 3.11+ from https://www.python.org/downloads/ (check **Add Python to PATH**).
2. Extract ZIP. Double-click `start-windows.bat`.
3. Open `http://127.0.0.1:8000` (localhost only). Initial installation downloads Python dependencies.
4. Open **ჩემი სივრცე**. Demo accounts below allow end-to-end workflow testing. Demo content is fictional and labeled.

**Demo identities** — password `DemoOnly!234` for all (NEVER use in publicly accessible deployment):

- `company@demo.sivrce.ge` — company, manage jobs, applications, interview scheduling, corporate briefs, select proposals and close vacancy.
- `provider@demo.sivrce.ge` — provider, create courses, cohorts, CSV-import authorized catalog, review learning inquiries and submit proposals.
- `candidate@demo.sivrce.ge` — candidate, save vacancies, submit/withdraw PDF applications, track interviews and course interests.
- `admin@demo.sivrce.ge` — moderator, review organizations and all submitted jobs/courses, curate Voices, administer content rights.

macOS/Linux: `bash start-mac-linux.sh` and open `http://127.0.0.1:8000`.

## What's implemented

**Careers:** identifiable verified companies; mandatory salary minimum/maximum and gross/net basis; purpose, responsibilities, qualifications and selection stages; candidate application with private PDF or portfolio URL; status tracking; saved jobs; candidate withdrawal and CV deletion; employer interview scheduling visible to candidate; vacancy closure; role-based ownership; admin moderation. Actual non-demo jobs receive Google JobPosting JSON-LD on the job detail page when still open.

**Learning:** complete provider course record, trainer, outcomes, curriculum, price, separate future cohorts, interest workflow (not a reservation or purchase), provider acceptance/decline, CSV provider catalog import requiring rights attestation and editorial moderation.

**Exchange:** corporate training briefs and confidential supplier proposals. Private briefs are not publicly discoverable. Full invitation, versioning and payments are NOT yet implemented.

**Voices & Journal:** official Spotify embeds with no autoplay, original publisher attribution, click-to-load player; 3 original Georgian editorial features in `/journal`; content-rights registry. **No third-party speaker voice cloning, full translation, or dubbing is performed.**

**Google login:** Google Identity Services credential verification implemented server-side; audience/issuer/email verification, subject-linked identity, explicit account linking for existing email accounts; **not enabled until configured** with your Google Cloud Web OAuth Client ID. This is not the same as company verification.

**Business:** benefits page with pilot lead form storing a local record (no auto-email/no charges). Actual provider quotes, subscription and billing are not present.

**Editorial design:** black/porcelain/cobalt, no green as a brand color; distinct Business/Journal sections; responsive and reduced-motion support. Static page visual checks were performed at desktop and mobile viewport sizes; real browser API flow was tested via API suite, but full interactive cross-browser visual QA remains a release prerequisite.

## Google setup

1. Create an OAuth Web application client on Google Cloud Console and configure its consent screen, branding, domains and authorized JavaScript origins.
2. For localhost test configure `http://127.0.0.1:8000` as authorized JavaScript origin (also `http://localhost:8000` if used).
3. Set the environment variable `GOOGLE_CLIENT_ID` to the **Web client ID** before starting the app (public identifier, not a secret). In Windows CMD: `set GOOGLE_CLIENT_ID=YOUR_CLIENT_ID.apps.googleusercontent.com` before running `start-windows.bat` in that shell, or add it to your own shell environment.
4. Login with Google appears only when enabled. Existing account emails must first log in with their original credential, then link the Google account inside Studio. This prevents automatic same-email account takeover.

## CSV template

UTF-8 CSV headers (one row per course; 1–50 records, max 256 KB):

```csv
title,category,format,description,outcomes,curriculum,trainer,price,duration
```

Each row must meet server validation. The provider explicitly attests rights. Verified providers' imported courses enter `pending_review`, never directly published.

## Security and deployment

`SEED_DEMO=1` creates fictitious accounts on empty local DB. **Never enable it in a public/staging environment.** Application uses hashed password/session tokens, SameSite+HttpOnly session, CSRF header on authenticated changes, protected private CV endpoints, verified organization ownership checks, audit entries and moderated publication. These measures are **not a production security certification**. SQLite is development only.

Before public launch: real organization verification; verified email, account recovery, retention/erasure policies, compliance review, production PostgreSQL with migrations and backups, safe PDF malware scanner and encrypted storage, rate limiting, CSP/security headers, monitoring, transactional notifications, robust privacy terms and independent penetration test. Payments and automated AI voice translations require separate integration and rights.

See [RELEASE_STATUS_KA.md](RELEASE_STATUS_KA.md), [CONTENT_RIGHTS_AND_GROWTH_KA.md](CONTENT_RIGHTS_AND_GROWTH_KA.md) and [WORK_HANDOFF.md](WORK_HANDOFF.md).

## Tests

`python -m pytest tests -q`

15 API/integration tests cover auth, CSRF, privacy boundaries, Google token/link logic (mocked, not live Google), job content validation, applicant upload/withdrawal, interview scheduling, cohort inquiries, CSV import and moderation, corporate proposals, content-rights controls, and pilot requests. Tests are not a substitute for security audit, load testing or live cross-browser QA.
