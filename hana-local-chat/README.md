# Hana Local Chat

A small, personal ChatGPT-style chat app that runs **only on your Windows computer**
using a local AI model through [Ollama](https://ollama.com). No accounts, no cloud,
no paid API, no API keys. It only chats - it cannot run commands, browse the web,
or take actions.

Built with plain HTML/CSS/JavaScript, Node.js + Express, and browser `localStorage`
(for saving chat history).

## What you need
1. **Node.js** (version 18 or newer): download the LTS version from https://nodejs.org
2. **Ollama for Windows**: download from https://ollama.com/download

## Install and start (Windows PowerShell)

Open PowerShell and check the tools are installed:

```powershell
node --version
npm --version
ollama --version
```

Download an AI model (one time; this is a few GB):

```powershell
ollama pull llama3.2
```

Go to the project folder, install, and start the app:

```powershell
cd path\to\Apps\hana-local-chat
npm install
npm start
```

Now open **http://localhost:3000** in your browser. Stop the app with `Ctrl+C`.

Ollama normally runs in the background after install. If you see
"Could not reach Ollama", start the Ollama app from the Start menu
(or run `ollama serve` in another PowerShell window).

## Using the app
- Type in the box and press **Send** (Enter sends, Shift+Enter makes a new line).
- **New Chat** starts a fresh conversation; **Delete Chat** removes the current one.
- Past conversations are listed in the sidebar (the ☰ button shows it on phones/small screens).
- Change the model in the **Ollama model** box (use any name from `ollama list`).

## Optional settings
Copy `.env.example` to `.env` to change the port, Ollama address, or default model:

```powershell
Copy-Item .env.example .env
```

## Privacy and safety
- The server listens on `127.0.0.1` only, so other computers cannot reach it.
- No passwords, tokens, or keys exist in the code. `.env` is git-ignored.
- Chats are stored in your browser only. Clearing browser data deletes them.

## Troubleshooting
| Problem | Fix |
| --- | --- |
| `npm` is not recognized | Reinstall Node.js, then open a new PowerShell window |
| Could not reach Ollama | Start Ollama (see above) |
| model "..." not found | Run `ollama pull <model>` or fix the model name |
| Port 3000 in use | Set `PORT=3001` in `.env` |

To learn how it works, read [PROJECT_GUIDE.md](PROJECT_GUIDE.md).
