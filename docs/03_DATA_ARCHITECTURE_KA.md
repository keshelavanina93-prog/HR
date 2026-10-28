# 03 — საინჟინრო არქიტექტურა: ბეტადან რეალურ მრავალმომხმარებლიან სისტემამდე

## 1. დღეს და სასურველი მიზანი

**დღევანდელი კოდი:** FastAPI + SQLAlchemy + Jinja + CSS/vanilla JS; development SQLite; session-cookie, CSRF, Argon2, protected CV, basic RBAC, Google token verification endpoint. ეს არის მართვადი ვერსია, მაგრამ არ არის production სტეკი.

**სასურველი არქიტექტურა:**

```text
Browser (KA-first responsive UI)
   │
   ├─ Public web: SSR / SEO pages, indexed verified jobs & courses
   ├─ Company workspace: job quality, pipelines, interviews, decisions
   ├─ Provider workspace: catalogs, cohorts, proposals
   └─ Candidate workspace: saved jobs, applications, profile
   │ HTTPS + secure sessions
API / FastAPI (versioned /v1)
   ├─ Identity & Organization / explicit permission checks
   ├─ Recruitment service / job quality & application workflows
   ├─ Learning catalog / sessions / enquiries
   ├─ Corporate procurement / briefs / invitations / proposals
   ├─ Content rights / editorial / localization
   ├─ Notifications & event outbox / workers
   ├─ Subscription entitlements / payments
   └─ Audit, consent, retention & exports
   │
PostgreSQL (primary, migrations, backups)
Object storage (private encrypted candidate files; signed time-limited URLs)
Queue / worker (email, imports, summarization, indexing)
Full-text search (Postgres FTS first; dedicated search later if needed)
Monitoring (logs, traces, errors, metrics) + error budget
```

**Frontend გადაწყვეტილება:** შეგიძლია დატოვო თანდათანობით გაუმჯობესებული server-rendered აპი ან შექმნა Next.js / TypeScript კომპონენტური frontend. მხოლოდ React-ის დამატება ვერ გააუმჯობესებს UX-ს. თუ Next.js-ს აირჩევ, გამოიყენე API კონტრაქტების მკაფიო საზღვრები და ეტაპობრივი migration, არა ყველა ბიზნესლოგიკის თავიდან დაწერა.

## 2. მონაცემთა მოდელი (სამიზნე) — ცხრილები და კავშირები

### Identity / governance

- `users(id, name, email, verified_at, password_hash?, status, locale, created_at)`
- `oauth_identities(user_id, provider, provider_sub, verified_at)` უნიკალური `(provider, provider_sub)`.
- `organizations(id, legal_name, public_name, tax_id, country, website, location, verification_status, created_at)`; ცალკე legal და public სახელები.
- `memberships(id, organization_id, user_id, role, status, invited_by)` unique org/user.
- `organization_branding(org_id, hero, logo, team_photos, permissions_manifest)` მხოლოდ უფლებებით.
- `audit_events(id, actor_id, org_id, action, entity_type, entity_id, before_json, after_json, at, ip_hash, request_id)` immutable append-only.
- `consent_events(id, user_id, purpose, policy_version, granted_at, revoked_at)`.
- `content_rights(id, content_type, content_id, source_url, rights_holder, usage_scope, evidence_doc_ref, expires_at, reviewer_id)`.

### Hire

- `job_posts(id, org_id, title, department, workplace, employment_type, compensation_min, compensation_max, currency, gross_net, purpose, responsibilities, requirements, nice_to_have, benefits, stages, deadline, publication_state, valid_from, updated_at, published_at)`.
- `job_versions(id, job_id, version_no, changed_by, snapshot, reason, created_at)`.
- `candidate_profiles(id, user_id, headline, skills, location, preferences, visibility)`.
- `applications(id, job_id, candidate_id, status, applied_at, withdrawn_at, data_retention_until)`.
- `application_documents(id, application_id, object_key, mime, malware_scan_status, retention_until)`.
- `application_events(id, application_id, actor_id, from_state, to_state, note, created_at)`.
- `interviews(id, application_id, starts_at, ends_at, timezone, format, location_or_link, organizer_id, status)`.
- `scorecard_templates(id, org_id, job_id, criteria_json)`; `scorecard_reviews(id, application_id, evaluator_id, criteria_values, note, finalized_at)` — ადამიანის შეფასება, არა ავტომატური საბოლოო გადაწყვეტილება.
- `candidate_messages(id, application_id, sender_id, recipient_id, body, delivery_status, created_at)`; არ შევინახოთ emails ისე, რომ სხვა კომპანიას წვდომა ჰქონდეს.

### Learning / procurement

- `providers(id, org_id, specialties, verification_state, cancellation_policy)`.
- `courses(id, provider_id, title, outcomes, curriculum, prerequisites, trainer_id, language, format, vat_policy, update_at, state)`.
- `course_sessions(id, course_id, starts_at, ends_at, timezone, capacity, seats_remaining, location, price_amount, currency, booking_state)`.
- `course_inquiries(id, session_id, user_id, state, created_at)`; ინტერესი ≠ ფასიანი ჯავშანი.
- `learning_briefs(id, org_id, goal, audience, budget_min, budget_max, delivery_format, region, deadline, visibility, status)`.
- `brief_invitations(id, brief_id, provider_id, invited_at, status)` — private visibility enforcement.
- `proposals(id, brief_id, provider_id, current_version, state, submitted_at)`.
- `proposal_versions(id, proposal_id, version, amount, currency, tax_included, training_hours, methodology, trainer_credentials, deliverables, exclusions, pdf_ref, created_at)`.
- `proposal_evaluations(id, proposal_version_id, evaluator_id, criteria, weighted_result, note, finalized_at)`; weights user-controlled, transparent.
- `awards(id, brief_id, proposal_id, decided_by, decision_reason, awarded_at)`.
- `delivery_engagements(id, award_id, dates, attendance_ref, acceptance, feedback)`.

### Product business & content

- `plans`, `subscriptions`, `entitlements`, `invoices`, `payment_events`, `usage_events` separated. Idempotent incoming bank/PSP webhook verification.
- `editorial_articles`, `episodes`, `article_sources`, `translations`, `localized_summary_versions`, `licenses`.
- `notifications(id, recipient_id, kind, payload, channel, status, sent_at)`, `notification_preferences`, `email_delivery_events`.
- `integration_connections(org_id, provider, permissions, last_sync_at, errors)`; encrypt secrets, separate provider-specific sync cursors.

## 3. Multi-tenancy და უფლებები

| მოქმედება | Candidate | Company Owner | Recruiter | Hiring Manager | Provider Owner | Moderator |
| --- | --- | --- | --- | --- | --- | --- |
| ნახოს საჯარო ვაკანსია | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| ნახოს კონკრეტული კომპანიის განაცხადები | — | ✓ | ✓ | მხოლოდ მინიჭებული ვაკანსია | — | მხოლოდ მხარდაჭერის კონტროლირებადი უფლებით |
| შექმნას/რედაქტირდეს ვაკანსია | — | ✓ | ✓ | შემოთავაზების დრაფტი | — | მოდერაციის შენიშვნები |
| გადაწყვიტოს კანდიდატის სტატუსი | — | ✓ | ✓ | მხოლოდ მინიჭებული საქმის ფარგლებში | — | — |
| საკუთარი განაცხადის გამოთხოვა | ✓ | — | — | — | — | — |
| შექმნას სასწავლო მოთხოვნა | — | ✓ | ორგანიზაციის მინიჭებული როლი | — | — | — |
| გამოგზავნოს შეთავაზება | — | — | — | — | ✓ | — |
| ნახოს სხვა მომწოდებლის კერძო შეთავაზება | — | მხოლოდ შემსყიდველ org-ში | — | — | — | — |
| გადაამოწმოს ორგანიზაცია | — | — | — | — | — | ✓ |

**შენიშვნა:** დღევანდელ კოდში Owner, Recruiter, Hiring Manager როლების სრული კონფიგურაცია ჯერ არ არის — ეს სამიზნე უფლებების მატრიცაა. გადამოწმების გარეშე კომპანიის პროფილის შექმნა არ ნიშნავს ავტომატურად გამოქვეყნების უფლებას.

ყველა ORM query უნდაფილტრავდეს `org_id`-ს ცხადად. სასურველია PostgreSQL Row-Level Security დამატებით კონტროლად, არა სერვერული უფლებების შემცვლელად. private brief-ს საჯარო ძებნის API არც metadata-ით არ უნდა გამოეპაროს.

## 4. Workflow state machine

**Vacancy**: `draft → quality_check → moderation → published → paused → closed → archived`. Rejected moderation returns to `draft` with required corrections. Unverified org cannot enter `published`.

**Application**: `received → screening → interview → offer → hired/rejected`, with `withdrawn` any pre-final stage. ყოველი ცვლილება არის event. Candidate messages use clear delivery status. ნუ გამოიყენებ გაუმჭვირვალე AI-წინასწარ უარყოფას.

**Training brief**: `draft → approved_for_distribution → published/invited → receiving → evaluating → awarded/cancelled → delivered → evaluated`.

**Proposal**: `draft → submitted → clarification_requested → revised → selected/not_selected → contracted`. ვერსია არასდროს გადაიწერება ჩუმად; ყოველი ცვლილება ინახება.

**Course**: `draft → verification_needed → moderated → published → updated → archived`; session lifecycle `scheduled → registration_open → full → completed/cancelled`.

## 5. APIs და ინტეგრაციის კონკრეტული კონტრაქტი

არსებული საბაზისო API-ები `server.py`-შია. სამიზნე ახალი endpoints:

```http
GET    /v1/orgs/{orgId}/inbox?status=requires-action
GET    /v1/orgs/{orgId}/activity?cursor=...
POST   /v1/orgs/{orgId}/invites
PATCH  /v1/orgs/{orgId}/members/{userId}
POST   /v1/jobs/{jobId}/review-request
POST   /v1/jobs/{jobId}/publish (server quality + editorial review)
GET    /v1/jobs/{jobId}/quality
GET    /v1/jobs/{jobId}/applications
PATCH  /v1/applications/{id}/stage
POST   /v1/applications/{id}/interviews
POST   /v1/applications/{id}/messages
GET    /v1/orgs/{orgId}/hiring-analytics
POST   /v1/briefs/{id}/invitations
POST   /v1/briefs/{id}/proposal-versions
POST   /v1/briefs/{id}/evaluation
POST   /v1/briefs/{id}/award
POST   /v1/courses/import/preview
POST   /v1/courses/import/commit
GET    /v1/notifications
POST   /v1/notifications/read
GET    /v1/content/rights/{id}
POST   /v1/billing/checkout-session
POST   /v1/billing/webhook (verified signature + idempotency)
```

All mutation requests: secure session, CSRF/origin, per-org permission, audit event, consistent error codes and server-side validation. API errors in KA with machine-readable `code` and `field_errors`, not raw exception strings.

## 6. ინტეგრაციები — საჭიროება და უსაფრთხო რიგი

| ინტეგრაცია | აუცილებლობა | საიდან მოდის კონფიგურაცია | სტატუსი |
| --- | --- | --- | --- |
| Google Identity Services | შესვლა | Google Cloud web client ID + verified origin | backend ნაწილი არსებობს; credentials აკლია |
| SMTP/provider transactional email | ინტერვიუ, მოთხოვნა, სტატუსი | provider account + sender domain/DKIM | სამიზნე |
| Google Calendar / Microsoft 365 | ინტერვიუების კალენდარი | OAuth consent, narrow scopes | სამიზნე |
| Google JobPosting / Indexing | კანდიდატების ორგანული მოზიდვა | verified canonical pages & valid markup | ნაწილობრივ არსებობს; live SEO QA საჭიროა |
| Payment service / Bank of Georgia or equivalent | კომპანიის გამოწერა | ხელშეკრულება, API keys, merchant credentials | არ არსებობს |
| Object storage / malware scanning | CV უსაფრთხოება | storage + scanner + lifecycle policy | მხოლოდ ლოკალური დაცული CV არის |
| AI provider | არასტრუქტურირებული ტექსტის მოწესრიგება | API key + DPA + redaction | ჯერ არა |
| ElevenLabs/other dubbing | ლიცენზირებული ეპიზოდის გახმოვანება | უფლებების მტკიცებულება + provider contract | არ არსებობს |
| Analytics/Error tracking | დაკვირვება | project tokens; cookie/consent policy | არ არსებობს |

Google backend token validation documentation: https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
Google JobPosting policy: https://developers.google.com/search/docs/appearance/structured-data/job-posting
Spotify Embed: https://developer.spotify.com/documentation/embeds

## 7. Non-functional / release controls

- HTTPS everywhere; production `Secure`, `HttpOnly`, `SameSite` cookies; CSRF defense; account recovery and email verification.
- `Alembic` migrations; PostgreSQL backups and restore test; no `create_all()` as production migration strategy.
- CV uploads: MIME + magic bytes + malware scan, size limits, encrypted object storage, signed links, short retention, audit downloads, legal deletion workflow.
- Role checks at API and DB; anti-IDOR tests for every endpoint; rate limits, login brute force protection; headers/CSP/CSRF.
- Search results must not include closed, expired, anonymous or unverifiable jobs.
- Monitoring for failed auth, 5xx, slow DB queries, jobs pending review, email failures.
- Performance goal (not measured): p75 page LCP <2.5s on representative mid-tier mobile, major actions p95 <1s server processing excluding network/payment; prove via lab and field metrics before claim.
- WCAG 2.2 AA as target; actual audit needed.
- Security review with local counsel for personal data, cross-border processors, applicant retention and deletion.
- Production deployment **blocked** until all critical vulnerabilities, unlicensed third-party content, missing privacy terms and unsafe demo credentials are resolved.
