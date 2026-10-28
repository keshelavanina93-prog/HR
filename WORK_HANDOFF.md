# SIVRCE 2026 — next steps for Work / Engineering

Use the **existing** source from this archive; do not replace with another static HTML concept. Design is black/porcelain/cobalt with no green. Preserve the policy that vacancies require verified, identifiable employers, pay ranges with gross/net, substantive role descriptions and human review. Paid accounts cannot bypass quality controls. The `CONTENT_RIGHTS_AND_GROWTH_KA.md` file defines ingestion and licensing guardrails.

## Verify first
1. `python -m pytest tests -q`: 15 tests run locally. Re-run after every change.
2. Launch with demo data, inspect all routes `/`, `/business`, `/careers`, `/learn`, `/exchange`, `/voices`, `/journal`, `/studio` and role-specific end-to-end paths on 320–1920px.
3. Validate Google account sign-in using **your own** configured Google OAuth Web Client ID, including existing-account linking; tests currently mock Google verification.
4. Review candidate CV privacy, abuse cases, race conditions and secure file upload. Do not put genuine CVs in demo.

## Release blockers — prioritize, do not claim done until proven
- Data protection/terms/privacy notice, account recovery, email verification, deletion/retention, legitimate interest/consent choices and operational data-subject handling.
- Migrate SQLite to PostgreSQL, migrations/backups, storage lifecycle, malware scanning, notifications and retry queues, observability and secure configuration.
- Secure and documented team member invitations, granular applicant review permissions and interview scheduling with calendar invites/notifications (currently only in-app records).
- Provider catalog updates/price versions, validity windows, registration/payment/invoicing, quote revisions, supplier comparison matrix, buyer/supplier negotiations and contract lifecycle.
- Verified real organizations, no misleading demo or seed data in public, content licensing/rights audit and trained moderation personnel.
- Full Georgian accessibility/typography and actual browser QA including keyboard, screen readers, high-contrast mode; capture and repair all visual defects.
- Secure billing with locally supported payment provider and legal terms; no payments are currently made or collected.
- If AI services are added: provider contract, data minimization, human oversight, explainability, costs and candidate fairness safeguards. No automated candidate rejection.
- Publishing dubbed third-party podcasts only after translation/reproduction/speaker voice rights are documented; currently only official embeds and original commentary.

## Commercial validation
Start with 10 directly invited employers and 10 course providers. Measure an actual hire flow and corporate training exchange before pricing. Track employer activation, valid vacancies, applicant completion and first-provider-response time. Avoid mass scraping or fabricated content.

## Proof limitations
Backend integration tests: 15 pass. Static browser rendering: desktop and mobile layouts inspected; one mobile overflow corrected. Chromium blocked network navigation to local server, so fully interactive visual browser QA and Google live auth were **not independently confirmed**. Do not represent this as production-complete or publicly deployed.
