// server.js - the small local server for Hana Local Chat.
// Job: serve the web page, and pass chat messages to Ollama and stream the answer back.

require('dotenv').config(); // reads optional settings from a ".env" file
const express = require('express');
const path = require('path');

const PORT = Number(process.env.PORT) || 3000;
const OLLAMA_URL = (process.env.OLLAMA_URL || 'http://localhost:11434').replace(/\/+$/, '');
const DEFAULT_MODEL = process.env.DEFAULT_MODEL || 'llama3.2';
// Safety: only listen on this computer, so other devices on the network cannot connect.
const HOST = '127.0.0.1';

const app = express();
app.use(express.json({ limit: '1mb' })); // lets us read JSON sent by the browser
app.use(express.static(path.join(__dirname, 'public'))); // serves index.html, style.css, app.js

// The browser asks for this to learn the starting model name.
app.get('/api/config', (req, res) => {
  res.json({ defaultModel: DEFAULT_MODEL });
});

// The browser sends { model, messages } here. We forward it to Ollama and stream the reply back.
app.post('/api/chat', async (req, res) => {
  const { model, messages } = req.body || {};

  // Basic checks so bad input gives a clear error.
  if (typeof model !== 'string' || !model.trim() || model.length > 100) {
    return res.status(400).json({ error: 'Please provide a model name.' });
  }
  if (!Array.isArray(messages) || messages.length === 0) {
    return res.status(400).json({ error: 'Please provide some messages.' });
  }
  // Only keep the fields we expect, and only allow normal chat roles.
  const cleanMessages = messages
    .filter((m) => m && ['user', 'assistant'].includes(m.role) && typeof m.content === 'string')
    .map((m) => ({ role: m.role, content: m.content }));
  if (cleanMessages.length === 0) {
    return res.status(400).json({ error: 'No valid messages were provided.' });
  }

  // If the browser disconnects (e.g. page closed), stop talking to Ollama.
  const controller = new AbortController();
  res.on('close', () => controller.abort());

  try {
    const ollamaResponse = await fetch(`${OLLAMA_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: model.trim(), messages: cleanMessages, stream: true }),
      signal: controller.signal,
    });

    if (!ollamaResponse.ok) {
      // Ollama explains problems like "model not found" in its reply.
      let detail = '';
      try {
        detail = (await ollamaResponse.json()).error || '';
      } catch (e) { /* ignore */ }
      return res.status(502).json({
        error: detail || `Ollama returned an error (status ${ollamaResponse.status}).`,
      });
    }

    // Ollama streams one JSON object per line. We pass the lines straight through.
    res.setHeader('Content-Type', 'application/x-ndjson');
    for await (const chunk of ollamaResponse.body) {
      res.write(chunk);
    }
    res.end();
  } catch (err) {
    if (controller.signal.aborted) return; // browser left; nothing to do
    if (res.headersSent) return res.end(); // already streaming; just stop
    res.status(502).json({
      error: 'Could not reach Ollama. Is it running? Try starting the Ollama app.',
    });
  }
});

app.listen(PORT, HOST, () => {
  console.log(`Hana Local Chat is running at http://localhost:${PORT}`);
  console.log(`Using Ollama at ${OLLAMA_URL}. Press Ctrl+C to stop.`);
});
