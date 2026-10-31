# 04 — მშენებლობის თანმიმდევრული Roadmap / Definition of Done

ეს დოკუმენტი არ არის დაპირება, რომ ყველა პუნქტი უკვე განხორციელებულია. არის **სამუშაოს ზუსტი რიგი**, რომლითაც SIVRCE-ს ადგილობრივი ბეტიდან რეალურ, ანგარიშვალდებულ კომერციულ პროდუქტამდე მიიყვან.

## 0. ძირითადი წესები

- ყოველ ფუნქციას უნდა ჰქონდეს owner, input, output, success state, failure state, authorization, acceptance test.
- ერთდროულად არ ააშენო 5 სახის marketplace; მაგრამ **არქიტექტურა** თავიდანვე უნდა ითვალისწინებდეს Hiring + Learning + Provider + Editorial.
- თითოეული კვირის ბოლოს გადამოწმებადია არამხოლოდ UI, არამედ end-to-end ოპერაცია.
- რას არ ვაბარებთ ტესტის გარეშე: Google რეალური login; email delivery; payments; კანდიდატის გადაწყვეტილება; invoice; უფლებების დამტკიცება; გასაუბრების invitations; live job publishing.

## P0 — Product contract, UX audit, trustworthy foundations

| ID | სამუშაო | მიღების პირობა |
| --- | --- | --- |
| P0-01 | Product contract და KPI definitions | დასახელებულია 4 persona, 2 ფასიანი workflow, 1 activation metric, 3 guardrail |
| P0-02 | Design tokens (no green) | კობალტი/ink/porcelain; ქართული ტიპოგრაფია; AA კონტრასტი და reduced motion |
| P0-03 | New Business entry | კომპანიას ≤1 წუთში შეუძლია გამოიყენოს დემო და გაიგოს გადახდის მიზეზი |
| P0-04 | Demo/live separation | ყველა sample label ჩანს; არანაირი საჯარო fake vacancy ან success metric |
| P0-05 | Product analytics events | `visit_business`, `open_preview`, `begin_job`, `pass_quality`, `finish_first_workflow` განსაზღვრულია, კონსენთის პირობებით |
| P0-06 | Git and environment policy | dev/staging/prod განცალკევებული; no credentials in repository; seed demo dev-only |

## P1 — Identity, organization, permissions

| ID | სამუშაო | მიღების პირობა |
| --- | --- | --- |
| P1-01 | Google Sign-In live | რეალური Client ID, origin, signed token verify, account-linking conflicts tested |
| P1-02 | Email registration and recovery | ვერ ხდება ბოროტად გამოყენება, recovery token expires; email verification |
| P1-03 | Company verification | ს/კ, საიტი, წარმომადგენელი, review queue, approval/rejection notes |
| P1-04 | Team invites + role management | Owner, Recruiter, Hiring Manager, Procurement, Provider Editor; tests deny cross-org |
| P1-05 | Consent and privacy flows | მიზნის აღწერა, export/delete/retention, audited withdrawal |
| P1-06 | PostgreSQL migration | Alembic migration + restore rehearsal + no prod SQLite fallback |

## P2 — Hire, real candidate cycle

| ID | სამუშაო | მიღების პირობა |
| --- | --- | --- |
| P2-01 | Company career page | გადამოწმებული სახელწოდება, კანონიერი ფოტო, განახლებული ვაკანსიები, culture only grounded |
| P2-02 | Quality job builder | server blocks missing salary/gross-net, purpose, responsibilities, requirements, selection steps |
| P2-03 | Moderation queue | publish only when verified + approved; rejection reason visible |
| P2-04 | Candidate account + profile | candidate can view, update and withdraw own profile; email visibility controlled |
| P2-05 | Secure apply and CV | signed storage, malware scan, size validation, consent, per-org access |
| P2-06 | ATS pipeline | received/reviewing/interview/offer/hired/rejected/withdrawn, state history and undo rules |
| P2-07 | Interview scheduler | timezone Asia/Tbilisi, conflict check, invite and cancellation notifications |
| P2-08 | Scorecards and notes | human ratings, team permissions, no hidden AI decision |
| P2-09 | Candidate feedback system | response timestamps and configurable email templates; delivery confirmed |
| P2-10 | Hiring analytics | valid time-to-stage, conversion denominators, audit source; no fabricated ROI |
| P2-11 | Job SEO and expiration | JobPosting schema leaf page only; expired closed and removed from active listing |

## P3 — Develop / provider / training exchange

| ID | სამუშაო | მიღების პირობა |
| --- | --- | --- |
| P3-01 | Provider verification and portfolio | registration/company, course right to publish, instructor evidence |
| P3-02 | Course + session model | same course multiple cohorts, price, places, timezone, cancellation terms |
| P3-03 | CSV/XLSX import preview | schema validation, rows diff, rights attestation, rollback on failure |
| P3-04 | Corporate Brief Wizard | goal, audience, budget, timing, location, expected outcomes and disclosure control |
| P3-05 | Invitation / controlled visibility | private brief only invited providers, with tests |
| P3-06 | Clarification Q&A | immutable questions, answers, deadline, authorized parties |
| P3-07 | Proposal versions | price, VAT, delivery, trainer, methodology, conditions; append-only revisions |
| P3-08 | Comparison workbench | criteria adjustable by buyer, standardized matrix, human approval |
| P3-09 | Award and post-delivery evaluation | explicit decision, vendor notified, project history and completion report |
| P3-10 | Course registration/payment later | do NOT label interest as booking; financial integration as separate phase |

## P4 — Notifications / AI / localization

| ID | სამუშაო | მიღების პირობა |
| --- | --- | --- |
| P4-01 | Transactional email | send actual email on stage changes / invites / proposals, provider delivery receipts |
| P4-02 | In-app action inbox | dedupe events, deadlines, mark read/done, user settings, no ghost alerts |
| P4-03 | Georgian AI-assisted job writing | only suggests from employer's verified inputs; shows uncertainties and edits |
| P4-04 | Compare assistant for proposals | grounds each comparison to proposal version; never invent fields |
| P4-05 | Semantic search / taxonomy | normalize Georgian/English skill names; precision and synonym tests |
| P4-06 | Journal editorial CMS | author, source manifest, revision, proofread, publication schedule |
| P4-07 | Georgian commentary for Voices | original independent analyses, publication review, source link |
| P4-08 | Licensed translation/dubbing | signed usage rights; human QA; identified synthetic audio; no unsanctioned voice cloning |

## P5 — Billing, analytics, commercial operation

| ID | სამუშაო | მიღების პირობა |
| --- | --- | --- |
| P5-01 | Product entitlements | server-side limit per plan, trial start/end, cancel, grace period |
| P5-02 | Payment gateway | approved merchant, sandbox and live separate, signature, idempotent webhook |
| P5-03 | Invoices/VAT handling | taxation reviewed by local accountant, downloadable documents |
| P5-04 | Customer support | in-product support, issue tracking, data request handling, SLA |
| P5-05 | Founder operating metrics | activation by cohort, first value time, weekly jobs/briefs completed, paid retention |
| P5-06 | Pilot-to-paid transition | explicit offer, value evidence, consent, no automatic charge surprises |

## P6 — Launch hardening and reliability

| ID | სამუშაო | მიღების პირობა |
| --- | --- | --- |
| P6-01 | Independent security review | critical/high issues resolved; organization isolation and CV privacy tested |
| P6-02 | Load and failure tests | representative concurrent user journeys and queue failures covered |
| P6-03 | Backup/restore | restore into isolated environment checked; recovery strategy documented |
| P6-04 | Accessibility | WCAG 2.2 AA audit, keyboard-only flows and screen readers |
| P6-05 | Responsive/screenshot regression | 320/390/768/1024/1440 widths, major browsers, no horizontal overflow |
| P6-06 | Legal/data review | policies, agreements, content licensing, personal-data retention confirmed |
| P6-07 | Trial onboarding | 5 companies complete actual workflows without founder intervention |
| P6-08 | Public release gate | no demo identities, secrets, unlicensed content or fake listings in production |

## Definition of Done — ყველა დავალებისთვის

- User need demonstrated by a real scenario.
- UI interaction is wired to a secured API or *visibly* marked browser-only demo.
- Authorized success, unauthorized failure and validation error are tested.
- Empty/loading/error/success states exist in natural Georgian.
- No horizontal overflow at 320px; keyboard labels/focus; reduced motion.
- Audit event for business decisions; no silent data overwrite.
- Documentation and feature flag / rollout plan updated.

## Change control

`proposed → accepted → in progress → tested → reviewed → released`; ახალი ფუნქცია არ ნიშნავს დასრულებას სანამ test evidence და acceptance pass არ არსებობს. მიმღები (founder) ამოწმებს პროდუქტის ღირებულებას, UX-ს და რეალურ მონაცემებზე სიმართლეს; ტექნიკური პასუხისმგებელი ამოწმებს უსაფრთხოებას, migration-სა და logs-ს.
