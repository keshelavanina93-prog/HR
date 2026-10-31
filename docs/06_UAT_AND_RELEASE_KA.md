# 06 — ხარისხის ტესტები, UAT და Release Gate

## 1. პროდუქტის საბაზისო გასვლის ტესტები

| TEST | ნაბიჯები | მოსალოდნელი შედეგი | მიმდინარე მდგომარეობა |
| --- | --- | --- | --- |
| BIZ-01 | სტუმარი გახსნის `/business` | ხედავს არა აბსტრაქტულ დაპირებას, არამედ ბიზნესპროცესის პრევიუს და კონკრეტულ CTA-ს | HTML/CSS გაკეთებულია; end-user ვიზუალური QA საჭიროა |
| BIZ-02 | სტუმარი გახსნის `/business/experience` | საჩვენებელი გარემო მკაფიოდ მონიშნულია | template/JS გაკეთებულია; DOM browser E2E blocked in environment |
| BIZ-03 | დემოში შეცვლის განაცხადის ეტაპს | იცვლება Action Queue, Pipeline და Activity history; არ წერს real DB-ში | JS logic განხორციელებულია; manual browser test საჭიროა |
| BIZ-04 | შეავსებს ვაკანსიას | ხარისხის check-list იზრდება; salary missing ბლოკავს submit-ს | JS/Backend შემოწმება; browser E2E საჭიროა |
| BIZ-05 | შექმნის სასწავლო მოთხოვნას | goal/budget/deadline არის სავალდებულო; ინახება demo ან live draft | JS/Backend გზა; browser E2E საჭიროა |
| BIZ-06 | ცვლის ფასის კრიტერიუმს demo-ში | განმარტებადი შედარებითი ქულები იცვლება; რეალურად მიღებულ შეთავაზებებად არ ჩანს | JS logic განხორციელებულია |
| BIZ-07 | Owner შევა რეალურ ორგანიზაციაში | იღებს მხოლოდ საკუთარ კომპანიის მონაცემებს, სწორი API authorization | დაცული არსებული API; tests |
| BIZ-08 | სხვა ორგანიზაცია სცდის კანდიდატის სტატუსის შეცვლას | 403 | არსებული ინტეგრაციული ტესტი |
| BIZ-09 | კანდიდატი CV-ს გამოითხოვს/შლის | დოკუმენტზე წვდომა წყდება | არსებული ტესტი |
| BIZ-10 | Google login კონფიგურაციის გარეშე | არ ჩნდება ცრუ „Google ჩართულია“ დაპირება | backend config exists, frontend integration review needed |
| BIZ-11 | Provider აგზავნის proposal-ს | company sees it, another provider cannot see competitor private terms | backend integration tests target |
| BIZ-12 | Demo seed production | startup blocked | existing startup guard, production deployment hardening still needed |

## 2. ვიზუალური და ხელმისაწვდომობის QA

Test devices: 320×700, 390×844, 768×1024, 1024×768, 1440×900, 1920×1080. Chromium/Firefox/WebKit where available. Confirm: no horizontal overflow; Georgian text not clipped; modals close with Esc; keyboard tab order; focus visible; forms label inputs; minimal 44px hit targets; no color-only status; 200% zoom; reduced-motion; mobile sticky navigation; system font fallback if Google Fonts blocked.

**ამ გარემოში**: Playwright/Chromium-მა `file://` და `127.0.0.1` navigation administrator policy-ით დაბლოკა. ამიტომ არ არსებობს ამ turn-ში სანდო საბოლოო ვიზუალური screenshot-ები. **არ უწოდო პიქსელურად დადასტურებულს**, სანამ შეზღუდვის გარეშე არ გაიხსნება და QA ჩაივლის.

## 3. Security & privacy redlines

1. No public real CV collection until privacy policy, candidate retention, malware scanning, private object storage and secure deletion workflow exist.
2. No production SQLite and no seeded demo passwords. No marketing claims of verified business without proper verification.
3. Every `orgId`, `jobId`, `briefId`, `applicationId` path tested for IDOR with two companies + provider + candidate.
4. Google ID token server verification, origin/CSRF, safe account linking; never assume email alone proves org ownership.
5. Versioned proposals; no cross-provider leakage; no fake price comparisons in live workspace.
6. Payment webhook idempotency and financial reconciliation before selling subscriptions.
7. Moderated job publishing; no hidden salary; expired job autoclose; no misleading JobPosting schema.
8. AI never returns final hire/reject automatically; professional content publishing with rights and source evidence.
9. Backups and restoration tested; monitoring/alerting for failures; no secrets in repo.

## 4. Release verdict

**Current status: LOCAL BETA / PRODUCT & UX SYSTEM. NOT PUBLIC-RELEASE READY.**

Release criteria: all P1 + P2 critical flows production tested, P3 core supplier quotes controlled, legal and security sign-off, real Google connection, email, privacy, payment only when enabled, live content rights, design QA and pilot validation. Anything failing critical should block public launch. Do not accept „it renders“ as evidence of production readiness.

## 5. NEW onboarding smoke test

`/start` — guest selects registration → POST `/api/auth/register` → session cookie; completes company details → POST `/api/organizations` → POST verification request (only if complete). Returning account chooses login; if company exists, can open workspace. Google button is not displayed as connected unless `/api/auth/google/config` explicitly enables it. Company verification is a separate moderation state. Verify in normal desktop/mobile browser before release.
