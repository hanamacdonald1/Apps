// app.js - the browser code: shows chats, saves them, and talks to our server.

// ---- 1. Grab the page elements we need ----
const $ = (id) => document.getElementById(id);
const sidebar = $('sidebar'), chatList = $('chat-list'), messagesEl = $('messages');
const statusEl = $('status'), form = $('chat-form'), input = $('message-input');
const sendBtn = $('send'), modelInput = $('model-input'), titleEl = $('chat-title');

// ---- 2. App state, saved in the browser's localStorage ----
const STORAGE_KEY = 'hanaLocalChat.chats';
const MODEL_KEY = 'hanaLocalChat.model';
let chats = loadChats();      // [{ id, title, messages: [{role, content}] }]
let currentId = null;         // id of the chat being shown
let busy = false;             // true while waiting for a reply

function loadChats() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return Array.isArray(saved) ? saved : [];
  } catch (e) {
    return []; // damaged data: start fresh instead of crashing
  }
}
function saveChats() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(chats));
}
const currentChat = () => chats.find((c) => c.id === currentId);

// ---- 3. Drawing things on the page ----
function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.className = 'status' + (isError ? ' error' : '');
}

function renderSidebar() {
  chatList.innerHTML = '';
  for (const chat of chats) {
    const li = document.createElement('li');
    li.textContent = chat.title; // textContent (not innerHTML) keeps text safe
    li.title = chat.title;
    if (chat.id === currentId) li.className = 'active';
    li.onclick = () => { if (!busy) { currentId = chat.id; render(); sidebar.classList.remove('open'); } };
    chatList.appendChild(li);
  }
}

function addBubble(role, text) {
  const div = document.createElement('div');
  div.className = 'bubble ' + role;
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function renderMessages() {
  messagesEl.innerHTML = '';
  const chat = currentChat();
  titleEl.textContent = chat ? chat.title : 'New chat';
  if (!chat || chat.messages.length === 0) {
    // Friendly empty state
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.innerHTML = '<h2>Hi Hana! 👋</h2><p>Your chats stay on this computer. Type a message below to start.</p>';
    messagesEl.appendChild(empty);
    return;
  }
  chat.messages.forEach((m) => addBubble(m.role, m.content));
}

function render() {
  renderSidebar();
  renderMessages();
  setStatus('');
}

// ---- 4. Buttons ----
$('new-chat').onclick = () => {
  if (busy) return;
  currentId = null; // a chat is created when the first message is sent
  render();
  sidebar.classList.remove('open');
  input.focus();
};

$('delete-chat').onclick = () => {
  if (busy || !currentChat()) return;
  if (!confirm('Delete this chat? This cannot be undone.')) return;
  chats = chats.filter((c) => c.id !== currentId);
  saveChats();
  currentId = null;
  render();
};

$('menu-toggle').onclick = () => sidebar.classList.toggle('open');

modelInput.onchange = () => {
  localStorage.setItem(MODEL_KEY, modelInput.value.trim());
};

// Enter sends; Shift+Enter makes a new line
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
});

// ---- 5. Sending a message and streaming the reply ----
form.onsubmit = async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  const model = modelInput.value.trim();
  if (!text || busy) return;
  if (!model) { setStatus('Please enter a model name in the sidebar.', true); return; }
  localStorage.setItem(MODEL_KEY, model);

  // Create a chat on first message
  if (!currentChat()) {
    const chat = { id: String(Date.now()), title: text.slice(0, 40), messages: [] };
    chats.unshift(chat);
    currentId = chat.id;
  }
  const chat = currentChat();
  chat.messages.push({ role: 'user', content: text });
  saveChats();
  input.value = '';
  renderSidebar();
  renderMessages();

  busy = true;
  sendBtn.disabled = true;
  setStatus('Thinking...');
  const bubble = addBubble('assistant', '');
  let reply = '';

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, messages: chat.messages }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || 'The server returned an error.');
    }

    // The reply arrives in pieces; each line is a small JSON object.
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // last piece may be incomplete; keep it
      for (const line of lines) {
        if (!line.trim()) continue;
        const part = JSON.parse(line);
        if (part.error) throw new Error(part.error);
        if (part.message && part.message.content) {
          reply += part.message.content;
          bubble.textContent = reply;
          messagesEl.scrollTop = messagesEl.scrollHeight;
        }
      }
    }
    if (!reply) throw new Error('The model sent an empty reply.');
    setStatus('');
  } catch (err) {
    setStatus('Error: ' + err.message, true);
    if (!reply) bubble.remove();
  }

  // Save whatever we got (even a partial reply)
  if (reply) chat.messages.push({ role: 'assistant', content: reply });
  saveChats();
  busy = false;
  sendBtn.disabled = false;
  input.focus();
};

// ---- 6. Start up ----
async function start() {
  let model = localStorage.getItem(MODEL_KEY);
  if (!model) {
    try {
      model = (await (await fetch('/api/config')).json()).defaultModel;
    } catch (e) {
      model = 'llama3.2';
    }
  }
  modelInput.value = model;
  render();
}
start();
