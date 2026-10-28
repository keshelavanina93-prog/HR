# 08 — სამუშაო დავალება ChatGPT Work / Codex / საინჟინრო გუნდს

ქვემოთ მოცემული ტექსტი პირდაპირ შეიძლება გამოყენებულ იქნას როგორც ახალი პროექტის სისტემური დავალება. ჯერ ატვირთე ZIP. ნუ დაიწყებ ცარიელი პროექტიდან, სანამ არსებულ კოდს არ შეამოწმებ.

---

## Paste into Work

SIVRCE is a Georgian-first, premium professional talent-and-learning platform. I own this codebase and want a production-oriented, secure, coherent rebuild — NOT another static landing page, sample-only interface, SaaS dashboard kit or generic redesign.

Read the repository thoroughly and these source-of-truth documents in this exact order:

1. `START_HERE_KA.md`
2. `docs/01_PRODUCT_CONTRACT_KA.md`
3. `docs/02_EXPERIENCE_AND_COPY_KA.md`
4. `docs/03_DATA_ARCHITECTURE_KA.md`
5. `docs/04_BUILD_BACKLOG_KA.md`
6. `docs/05_CONTENT_RIGHTS_AND_GROWTH_KA.md`
7. `docs/06_UAT_AND_RELEASE_KA.md`
8. `docs/07_DESIGN_TOKENS.json`

The product has four connected experiences: Careers, Learning, Exchange, Voices/Journal; three private roles: Company, Provider, Candidate; plus moderators/admin. Company retention is built around genuine action queues, role-aware operational tasks, transparent vacancies, application pipelines, human interviews, structured training briefs, private proposals and auditable decisions.

Non-negotiable:
- NO GREEN in branding or component accents. Rich editorial public pages and precise, functional workspace UI.
- Georgian-first copy (correct Georgian, not generic AI slogans), English optionally later.
- Do not fabricate companies, salaries, applicant counts, testimonials, reviews, live podcast rights or real business results. All examples DEMO-labeled.
- No anonymous job, no job missing salary/gross-net/role/hiring steps; publishing behind verified employer + editorial gate.
- Never expose CV/application data across organizations. Every mutation requires authorization + audit.
- Google login must be truly wired to an owner-supplied Web OAuth Client ID; server token verification and safe account linking.
- Do not claim Spotify/YouTube content translation/dubbing rights absent signed licenses. Georgian independent analyses are okay after editorial/legal review.
- Do not accept real CVs or live payments until privacy, storage, malware scanning, merchant connection and security review are complete.

Implementation order: P0→P1→P2 core→P3 core, then other phases. Produce real, testable changes, not just a plan. At each step:
1. Locate actual source and explain the behavior being modified.
2. Implement frontend and API consistently with shared types and persistent data.
3. Add authorized/unauthorized/validation tests; add browser E2E and screenshot diff when browser is available.
4. Give exact localhost steps for manual verification.
5. Separate DONE, DEMO ONLY, BLOCKED BY CREDENTIALS, SECURITY/BUSINESS VALIDATION REQUIRED.
6. Do not mark a feature complete if it is only a button, a screenshot, an unsaved fake form, or an unverified API stub.

First engineering sprint: introduce safe PostgreSQL migration with Alembic, organization/team roles and invitations, secure and tested Google login config, email verification, job versioning and job quality state machine, application pipeline with human audit and notification outbox. Keep existing endpoints working during migration. Build the public website with thoughtful editorial hierarchy and actual, licensed content only.

Commercial outcome to measure: real companies completing a full hiring or learning procurement cycle, with proof of time/work saved; no monetization claim before validating actual willingness to pay.

---

## გასაზიარებელი ZIP-ის მოცულობა და პრიორიტეტი

არ გააზავო ყველა ფაზა ერთ დავალებაში ისე, რომ მხოლოდ pseudo-code დაბრუნდეს. Work-ში სჯობს ეტაპობრივად განხორციელდეს და ყოველი მონაკვეთის ბოლოს გადამოწმებული პროექტი დაიტესტოს. Founder/owner approves brand and copy; engineering owner approves security and data contract; legal advisor reviews rights/privacy/billing.
