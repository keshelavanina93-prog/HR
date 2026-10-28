# Development

This repository contains the existing SIVRCE Product Beta, imported from the supplied source package. FastAPI and SQLAlchemy serve the Jinja frontend in `templates/index.html`; browser behavior and styles live in `static/`. Preserve existing workflows when changing the UI.

## Local setup

Install Python 3.11 or newer and Git. Clone this repository, then run the appropriate local demo launcher:

```powershell
git clone https://github.com/keshelavanina93-prog/HR.git
cd HR
.\start-windows.bat
```

On macOS/Linux, use `bash start-mac-linux.sh`. Open `http://127.0.0.1:8000`. The launchers install `requirements.txt` into `.venv`, explicitly select development mode and seed a local demo database. They are local demo launchers; deployment needs a separate reviewed configuration.

For manual setup on Windows:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:APP_ENV = 'development'
$env:SEED_DEMO = '1'
$env:COOKIE_SECURE = '0'
.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000
```

`.env.example` documents configuration variables. The application does **not** automatically read `.env`; set variables in your shell or deployment runtime. The default database is a generated `sivrce.db` next to `server.py`. Demo logins are documented in README.md.

## Checks

After installing dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q server.py tests
.\.venv\Scripts\python.exe -m pytest tests -q
```

On macOS/Linux, replace the Python executable with `.venv/bin/python`. Tests create and reset their own `tests/integration-test.db`; run them serially. Test upload fixtures can create ignored `private_uploads/` files. Never use real candidate files for tests. CI runs the same checks on Python 3.11 and 3.13, using a fresh checkout and dependencies installed from `requirements.txt`.

## Change workflow

```powershell
git switch -c feature/describe-your-change
# Make and verify the change.
git add <specific-files>
git commit -m "Describe the resulting behavior"
git push -u origin HEAD
```

Open a pull request against `main`, describe the behavior and validation, and inspect the automated checks before merging. UI changes also need actual browser verification at relevant widths. Passing API tests does not prove visual quality, accessibility or production readiness. Repository branch protection is separate from this documented workflow and is not configured by the initial import.

## Data boundaries

Commit source and sanitized examples only. `.gitignore` excludes environment files, databases, virtual environments, caches and private uploads. Before pushing, inspect `git diff --cached` and `git status --short`. Do not force-add ignored data.

This beta has no public deployment or payment integration configured. See `WORK_HANDOFF.md` and `RELEASE_STATUS_KA.md` for outstanding product and release work. No license has been added; publishing source does not itself grant a reuse license.
