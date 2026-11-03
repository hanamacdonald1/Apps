# Project Guide: how a message travels

```
Browser (public/app.js)  ->  Server (server.js)  ->  Ollama (localhost:11434)
        ^                                                   |
        +---------------- streamed reply -------------------+
```

1. **You type and press Send.** `app.js` adds your message to the current chat,
   saves it to `localStorage`, and draws your bubble.
2. **Browser -> server.** `app.js` calls `fetch('/api/chat')` with the model name
   and the whole conversation (so the model remembers context).
3. **Server checks the request.** `server.js` makes sure the model name and
   messages look valid and keeps only `user`/`assistant` messages.
4. **Server -> Ollama.** The server sends the conversation to
   `http://localhost:11434/api/chat` with `stream: true`.
5. **Ollama answers in pieces.** It sends one small JSON line per few words.
6. **Server -> browser.** The server passes each piece straight through.
7. **Browser shows it live.** `app.js` reads each line, appends the text to the
   assistant bubble, and when finished saves the full reply to `localStorage`.

## Files
| File | Purpose |
| --- | --- |
| `server.js` | Local server; only listens on `127.0.0.1` |
| `public/index.html` | Page structure |
| `public/style.css` | Look, including mobile layout |
| `public/app.js` | Chat logic, sidebar, saving, streaming |
| `.env.example` | Optional settings (copy to `.env`) |

## Where is my data?
Only in your browser's `localStorage`. Clearing site data erases your chats.
There is no database, login, or cloud service.
