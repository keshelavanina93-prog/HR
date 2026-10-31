# SIVRCE — დახურული ბეტა Google Cloud-ზე (`beta.ncore.space`)

ერთი ვირტუალური სერვერი (Compute Engine, `e2-medium`, ფრანკფურტი) Docker-ით:
Caddy (ავტომატური HTTPS + საერთო პაროლი) → FastAPI → PostgreSQL 17, ClamAV CV-ების შესამოწმებლად, ღამის სარეზერვო ასლები Cloud Storage-ში.

**ეს ბეტაა, არა production.** DEMO მონაცემები ჩართულია, მთელი საიტი პაროლითაა დაცული და საძიებო სისტემებისთვის დამალულია (`noindex`). რეალურ კანდიდატებს აქ ნუ მოიწვევ.

## ნაბიჯები

ყველაფერი სრულდება **Google Cloud Shell**-ში: <https://shell.cloud.google.com> (იქ უკვე შესული ხარ შენი ანგარიშით).

### 1. კოდის ჩამოტვირთვა Cloud Shell-ში

```bash
git clone https://github.com/keshelavanina93-prog/HR.git && cd HR
```

### 2. პროექტი, სერვერი, IP, საცავი

```bash
bash deploy/gcp/provision.sh
```

ქმნის ახალ პროექტს (`sivrce-beta-YYMMDD`), აბამს შენს ბილინგის ანგარიშს (სადაც კრედიტებია), ქმნის სერვერს, მუდმივ IP-ს, firewall-ს და სარეზერვო bucket-ს. ბოლოს დაბეჭდავს IP მისამართს.

### 3. DNS

დომენის მართვის პანელში დაამატე:

| ტიპი | სახელი | მნიშვნელობა | TTL |
|---|---|---|---|
| A | `beta` | provision.sh-ის დაბეჭდილი IP | 300 |

Cloudflare-ზე: „DNS only“ (ნაცრისფერი ღრუბელი), თორემ სერტიფიკატი ვერ აიღება.

### 4. გაშვება

```bash
PROJECT_ID=sivrce-beta-YYMMDD ADMIN_EMAIL=შენი@ელფოსტა bash deploy/gcp/deploy.sh
```

პირველ გაშვებაზე სერვერი თავად აგენერირებს საიდუმლოებებს და **ერთხელ** დაბეჭდავს:
- ბეტას საერთო შესვლა (`sivrce` / პაროლი) — ეს გადაეცი სატესტო მომხმარებლებს;
- შენი მოდერატორის ანგარიში;
- დემო ანგარიშების ახალი პაროლი (რეპოზიტორიაში დაწერილი `DemoOnly!234` აქ აღარ მუშაობს).

შეინახე პაროლების მენეჯერში. საიდუმლოებები ინახება მხოლოდ სერვერზე: `/opt/sivrce/deploy/beta/.env` (წვდომა მხოლოდ root-ს).

### პაროლები დაიკარგა?

```bash
PROJECT_ID=sivrce-beta-YYMMDD bash deploy/gcp/credentials.sh
```
ქმნის **ახალ** ბეტას პაროლს (ძველი აღარ იმუშავებს) და ერთხელ ბეჭდავს მოდერატორისა და დემო ანგარიშების პაროლებს. მოდერატორის ელფოსტის შესაცვლელად დაამატე `ADMIN_EMAIL=ახალი@ელფოსტა`.

### განახლება

კოდის ცვლილების შემდეგ იგივე ბრძანება (`deploy.sh`) ხელახლა: ჩამოტვირთავს `main`-ს, ააწყობს, გაუშვებს მიგრაციებს. საიდუმლოებები არ იცვლება. სხვა ბრანჩისთვის: `BRANCH=sivrce-dev`.

## სურვილისამებრ

სერვერზე (`gcloud compute ssh sivrce-beta --zone europe-west3-a`) შეცვალე `/opt/sivrce/deploy/beta/.env` და გაუშვი `deploy.sh` თავიდან:

- **Google-ით შესვლა** — `GOOGLE_CLIENT_ID`. Google Cloud Console → APIs & Services → Credentials → OAuth client ID (Web), Authorized JavaScript origin: `https://beta.ncore.space`.
- **ელფოსტა** — `SMTP_HOST`, `SMTP_FROM`, `SMTP_USER`, `SMTP_PASSWORD`. მითითებისას ავტომატურად ჩაირთვება გამგზავნი (`worker`). მანამდე წერილები რიგში ინახება და არ იგზავნება.

## Google-ით შესვლა და ელფოსტა (სკრიპტით)

```bash
PROJECT_ID=sivrce-beta-YYMMDD bash deploy/gcp/configure.sh google   # ითხოვს Web client ID-ს და ამოწმებს
PROJECT_ID=sivrce-beta-YYMMDD bash deploy/gcp/configure.sh mail     # ითხოვს App Password-ს და აგზავნის სატესტო წერილს
```
ელფოსტა იგზავნება Google Workspace-ის SMTP-ით (`smtp.gmail.com:587`, STARTTLS) ანგარიშიდან `connect@nyxcore.space`. App Password: <https://myaccount.google.com/apppasswords> (საჭიროა 2-ნაბიჯიანი დადასტურება).

## Voices — ქართული პოდკასტების ინდექსი

- გაშვებისას სერვერი ერთხელ აინდექსებს საწყის სიას (`features/voices_starter.py`, 21 ქართული შოუ) და ყოველ საათზე აახლებს ფიდებს (`/etc/cron.d/sivrce-voices`).
- ახალი შოუს დამატება მოდერატორის ანგარიშით: `POST /api/admin/shows {"feed_url": "...", "topic": "work"}`. თემები: `work, science, society, culture, growth, other`.
- ქართული კონსპექტი, მთავარი აზრები და თავები: `PATCH /api/admin/episodes/{id}`.
- ტრანსკრიფცია (ElevenLabs Scribe v2, ქართული — მაღალი სიზუსტის ენა): `.env`-ში `ELEVENLABS_API_KEY=...`, შემდეგ `POST /api/admin/episodes/{id}/transcribe`. ფონური პროცესი 15 წუთში ერთხელ ამუშავებს რიგს. სრული ტრანსკრიპტი საჯაროდ ჩანს მხოლოდ გამომცემლის მიერ დადასტურებულ შოუებზე; დანარჩენებზე მხოლოდ ძებნას კვებავს.
- გამომცემლის დადასტურება: მფლობელი `POST /api/shows/{id}/claim`, მოდერატორი `PATCH /api/admin/shows/{id} {"claim": "approve"}`.

## სარეზერვო ასლები

ყოველ ღამე 03:15 UTC: PostgreSQL dump + ფოტოები + CV-ები → `gs://<PROJECT_ID>-backups/<თარიღი>/`. Bucket პირადია, ასლები 30 დღეში იშლება. ხელით: `sudo sivrce-backup`.

აღდგენა (სერვერზე):
```bash
cd /opt/sivrce && gcloud storage cp -r gs://<PROJECT_ID>-backups/<თარიღი> /tmp/restore
docker compose -f deploy/beta/compose.yml --env-file deploy/beta/.env exec -T database pg_restore -U sivrce -d sivrce --clean < /tmp/restore/<თარიღი>/sivrce.dump
```

## ღირებულება

`e2-medium` + 40 GB დისკი + მუდმივი IP + მცირე საცავი — დაახლოებით $30–35 თვეში (ზუსტი ფასი რეგიონზეა დამოკიდებული: Google Cloud Pricing Calculator). იხარჯება კრედიტებიდან.

## რა შემოწმდა გაშვებამდე

ზუსტად ეს კომპლექტი (იგივე `compose.yml` და `Caddyfile`) ლოკალურად გაეშვა `localhost`-ზე:
- სამივე მიგრაცია PostgreSQL 17-ზე; აპლიკაცია `/ready`;
- პაროლის გარეშე 401, HTTP → HTTPS გადამისამართება, HSTS და `noindex`;
- დემო ანგარიშზე ძველი პაროლი უარყოფილია, ახალი მუშაობს; სესიის cookie — `Secure` და `HttpOnly`;
- უცხო Origin-იდან მოთხოვნა 403; ფოტოს ატვირთვა; CV-ის ატვირთვა ClamAV-ის გავლით;
- სარეზერვო ასლი და მისგან ბაზის აღდგენა.

რაც ვერ შემოწმდა: `provision.sh` და `deploy.sh` რეალურ Google Cloud ანგარიშზე, და Let's Encrypt სერტიფიკატი რეალურ დომენზე.

## Production-მდე დარჩენილი

იხ. `docs/06_UAT_AND_RELEASE_KA.md`: კონფიდენციალურობის პოლიტიკა და პირობები, იურისტის შემოწმება, DEMO-ს გარეშე `APP_ENV=production`, მონიტორინგი, მოვლის პროცედურები.
