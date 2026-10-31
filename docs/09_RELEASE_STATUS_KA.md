# 09 — SIVRCE v5 / რეალური შესრულების ანგარიში

**Generated:** 2026-10-28. **Verdict:** Local functional beta + new interactive company experience. Public production release is BLOCKED.

## ამ სესიაში განხორციელებული

- `/business`: სრულად ახალი კომპანიისთვის განკუთვნილი დამარწმუნებელი გვერდი, არა წინა ზოგადი 3 ტექსტური პარაგრაფი.
- `/start`: ახალი კომპანიის onboarding (login/registration/org creation/verification request) და Google GIS conditional initialization; live Google config not present.
- `/business/experience`: ახალი action-driven სამუშაო UI, გამიჯნული დემო/რეალური რეჟიმით.
- Overview action queue + pipeline counts, no fabricated production metrics.
- Demo candidate pipeline with stage transitions and a visible action history (browser localStorage only).
- Vacancy form and live quality checklist, server-compatible fields. Demo publish doesn't actually publish. Live submits through protected POST `/api/jobs`, subject to server permissions and moderation.
- Training brief form and preview; live saves a private/public draft through POST `/api/briefs`.
- Training proposal comparison: demo weighting formula disclosed; live displays real org proposals with a protected selection action.
- Old site homepage hero copy refined, company CTA links to actual experience.
- Neutral/porcelain/cobalt palette (green brand removed from new screens); no fake portraits.
- Full Georgian product contract, sitemap, engineering architecture, permissions, release backlog, rights/growth, test plan and Work handoff.

## წინა ბეტადან შენარჩუნებული და ხელახლა დატესტილი

FastAPI secured sessions, basic org separation, CV privacy/withdrawal, company/provider separation, Google token handler (not configured live), course/cohort models, provider CSV import, editorial moderation, journal and rights registry. Tests remain green.

## დაბლოკილი / დაუსრულებელი

- True Google Identity integration needs your Google Cloud Client ID, allowed origins and domain verification.
- Real payments/subscriptions, invoice issuing, transactional email, provider search integration and calendar scheduling are not live.
- CV storage production hardening, independent security audit, DB migrations, PostgreSQL infrastructure and live cloud deploy are not done.
- Company team invitations, multi-role policy and granular recruiter permissions require new data model and API implementation.
- Podcast full Georgian translation and real-speaker voice cloning are not implemented and require rights.
- No real Georgian catalog/companies have been ingested from uncontrolled third-party sources. Demonstration company, provider, applications and offers are samples.
- Full visual Chromium QA was attempted, but both localhost and file navigation were blocked by admin policy. Static route/API tests passed; manual and real browser E2E still required.
- Not yet proven that paying customers value the product; pricing remains a research hypothesis.

## TEST REPORT

Run: `python -m pytest tests -q`. Output at creation: **18 passed**, warnings for deprecated `datetime.utcnow()` in legacy code. New company route and demo-read-only tests added. `node --check static/workbench_v5.js` passed.

**Do not deploy publicly and claim production readiness based on this test count alone.**
