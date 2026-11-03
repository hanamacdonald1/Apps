# Hana AI

A local personal assistant with a tool-calling coordinator, autonomous job scout, inbox and subscription scanners, an approval queue, and a background scheduler.

## Start on Windows

1. Install Python 3.11+ from [python.org](https://www.python.org/downloads/) and Ollama from [ollama.com](https://ollama.com/download).
2. Run `ollama pull qwen3:4b` in PowerShell for a local tool-capable model.
3. Download this repository as a ZIP, extract it, and double-click **Start-Hana-AI.cmd**.
4. In the app, open **Settings** to connect job sources and email accounts. See [SETUP.md](SETUP.md) for account registration instructions.
5. Save a schedule and enable agent actions. Keep the worker window open and your computer awake.

Dashboard buttons work without an AI model; model-led tool selection requires Ollama. No paid LLM API is required. Download, hardware, electricity, provider quotas and optional hosting costs still apply.

## What works

| Component | Implemented behavior |
|---|---|
| Coordinator | Local model chooses from bounded scanning and reading tools; up to four tool executions per turn |
| Job scout | Queries Adzuna Australia and configured RSS/Atom sources, ranks keyword coverage, deduplicates links, preserves application stages |
| Inbox agent | Reads recent metadata/previews from Gmail and Outlook; saves job alerts and subscription signals |
| Subscription agent | Finds likely subscriptions and prepares human-authored cancellation requests for review |
| Action worker | Sends an approved exact cancellation email through Gmail or Outlook; records submission or uncertain delivery |
| Scheduler | Runs configured scans at intervals while `worker.py` is running; SQLite lease prevents overlapping scheduler runs |
| Dashboard | Chat, jobs, inbox, subscriptions, actions, settings and activity log |

## Boundaries

- Gmail and Microsoft require **your own OAuth app registrations and sign-in**. ChatGPT connections cannot be reused by this app.
- No fabricated job listings or sample subscriptions are displayed.
- Job scores are explainable keyword coverage, not semantic resume scoring or hiring probability. Ask the coordinator to compare retrieved results with your saved resume text for a qualitative assessment.
- Email scan is bounded to up to 50 recent messages per account per run. Gmail uses the last 30 days; Outlook uses the most recent 50 messages. This is not a complete historical mailbox audit.
- No generic browser automation, arbitrary shell execution, job-application sending or account-portal cancellation is implemented.
- Cancellation **requests** can be sent autonomously after exact-message approval. A request is never reported as proof of cancellation. For portals requiring interactive cancellation, use the service portal directly.
- Pending actions cannot be sent by the model. Email and job content never grants permission.
- Unknown delivery and interrupted `sending` states require checking Sent mail; there is no automatic resend.
- Pausing stops new scheduled tasks and queued sends; an already in-flight network request can finish.
- There is no public deployment, user login or multi-user isolation. Bind the app to loopback and use it on your own computer.

## Local data

OAuth refresh tokens and Adzuna keys use the OS credential vault via `keyring`. The database in `~/.hana-ai/hana.db` contains local email previews, job records, background notes, settings, action payloads and activity. Chat is session-only. Do not commit local data or credentials; `.gitignore` excludes common secret files. Removing a local connection does not revoke the provider-side grant or erase previously stored previews; use provider settings to revoke access and delete the local data directory to erase this app's records.

## Validation

`python -m pip install -r requirements.txt pytest`

`python -m pytest -q`

CI checks syntax, agent execution limits, evidence-based tool use, source failures, deduplication, schedule controls, exact approvals, duplicate-send prevention, uncertain-delivery behavior and dashboard startup. Provider calls are mocked in automated tests. Live OAuth, live job sources and local-model inference require user configuration and are not certified by these tests.

## Native desktop edition (v0.2)

The repository now includes a native **PySide6 / Qt Widgets** desktop app in `desktop.py`. It starts no browser server. The desktop app runs its scheduler in-process, keeps working from its system tray when closed, refreshes saved results every two seconds and reports asynchronous tool progress without blocking the window. Only one desktop instance can run per data directory.

### Install

Open the latest successful **Build desktop installer** run under Actions. Download **HanaAI-Windows-Installer**, unzip it and run `HanaAI-Setup.exe`. The portable artifact contains `HanaAI.exe` and its adjacent runtime folder; keep those together. Python and Qt are bundled, so normal installed use requires no terminal. Windows builds are unsigned previews. The build workflow smoke-tests the actual bundled executable before compiling the installer.

The first-run guide points to Settings. A built-in Remotive source can find remote jobs without an API key; it preserves attribution and original links, filters for Australia/worldwide/APAC labels and observes a shared six-hour request budget. Provider listings are delayed by 24 hours, so the interface explicitly distinguishes live progress from listing freshness. Check eligibility on the original page. Adzuna and feeds provide additional sources.

### Money this week

The income scout scans its own job phrases and feeds plus saved email previews. It rejects explicit unpaid offers and low-value AUD project/day offers below your chosen minimum (at least A$100). Explicit hourly or annual salaries and ambiguous currencies are not labelled as meeting a per-booking target. Missing payment dates, costs and net earnings stay unknown. Matching service packages are suggested separately from real listings, with quotes explicitly labelled as unvalidated. No clients or earnings are invented.

### Native features

- Nine screens, light/dark themes, background tasks, tray controls and a global pause.
- Model download through an existing local Ollama server, with actual download progress.
- Resume text/PDF import, editable profile, filters, application stages and income target.
- Gmail/Outlook OAuth connection, recent inbox scans and reviewed cancellation email submissions.
- Quiet-hour notifications that omit private message content, local JSON export and record deletion.
- Own OAuth app registrations remain required. No generic account-portal cancellation or job-application submission is implemented.
- Closing to the tray preserves scheduling; **Quit** stops new work. An in-flight request may finish. Computer sleep/offline time prevents background work. This is not a hosted always-on service.

For development: `pip install -r requirements-desktop.txt`, then `python desktop.py`. The previous Streamlit entry point remains available as a legacy interface. Do not run a separate `worker.py` alongside the desktop edition; it already owns a scheduler (the shared lease also prevents overlap).

Qt is used as dynamically linked shared libraries in an onedir build. See [THIRD_PARTY.md](THIRD_PARTY.md) for dependency notices and source links.
