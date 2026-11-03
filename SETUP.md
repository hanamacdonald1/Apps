# Hana AI setup

Personal local chat with ADHD-friendly replies, task breakdowns and a pasted job-ad helper. No live job search or autonomous actions yet.

## Windows

1. Install Python 3.11+ from https://www.python.org/downloads/ and enable Add Python to PATH.
2. Install and open Ollama from https://ollama.com/download.
3. In PowerShell run `ollama pull llama3.2:3b`.
4. Download this repository using Code > Download ZIP, then extract it.
5. Open PowerShell in the extracted folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Open the local URL shown. Keep Ollama running and choose an installed model in the sidebar.

## Scope

No API key or ChatGPT subscription is needed. Local model inference has no per-message AI fee; internet, electricity and hardware still have costs. Initial setup requires downloads.

History and notes are session-only, with no database or persistent memory. Paste resume text and a job advertisement for comparisons. No uploads, live web search, accounts, or application sending are implemented. The app calls Ollama at 127.0.0.1 only. Keep it local until authentication is added.

This repository is public: do not commit personal documents or credentials.

## Workflow

Check app runs on pushes, pull requests or manually from Actions. It installs dependencies, checks Python syntax and tests interface startup without Ollama. It does not host the app or run the AI. GitHub Actions use is subject to GitHub account policies.
