// app.js
/* ---------- Guard ---------- */
const token = localStorage.getItem('token');
if (!token) {
  window.location.href = '/index.html';
  throw new Error('No token');
}

/* ---------- API helper ---------- */
const api = {
  async request(path, options = {}) {
    const res = await fetch(path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...(options.headers || {}),
      },
    });
    if (res.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/index.html';
      throw new Error('Unauthorized');
    }
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
    return body;
  },
  me: () => api.request('/api/me'),
  listConversations: () => api.request('/api/conversations'),
  createConversation: () =>
    api.request('/api/conversations', { method: 'POST', body: JSON.stringify({ title: 'New chat' }) }),
  getConversation: (id) => api.request(`/api/conversations/${id}`),
  deleteConversation: (id) =>
    api.request(`/api/conversations/${id}`, { method: 'DELETE' }),
  sendMessage: (id, content) =>
    api.request(`/api/conversations/${id}/chat`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    }),
};

/* ---------- State ---------- */
const state = {
  user: null,
  conversations: [],
  activeId: null,
};

/* ---------- DOM ---------- */
const el = {
  convList: document.getElementById('conversation-list'),
  messages: document.getElementById('messages'),
  emptyState: document.getElementById('empty-state'),
  chatTitle: document.getElementById('chat-title'),
  chatSubtitle: document.getElementById('chat-subtitle'),
  composer: document.getElementById('composer'),
  input: document.getElementById('composer-input'),
  sendBtn: document.getElementById('send-btn'),
  newChatBtn: document.getElementById('new-chat-btn'),
  logoutBtn: document.getElementById('logout-btn'),
  userName: document.getElementById('user-name'),
  userEmail: document.getElementById('user-email'),
  userAvatar: document.getElementById('user-avatar'),
};

/* ---------- Helpers ---------- */
function escapeHtml(str) {
  return str.replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
  );
}

function initials(name) {
  return name.split(/\s+/).map((p) => p[0]).join('').slice(0, 2).toUpperCase();
}

function autoResize(ta) {
  ta.style.height = 'auto';
  ta.style.height = Math.min(ta.scrollHeight, 160) + 'px';
}

function updateSendButton() {
  el.sendBtn.disabled = !el.input.value.trim() || !state.activeId;
}

/* ---------- Rendering ---------- */
function renderConversations() {
  el.convList.innerHTML = '';
  if (state.conversations.length === 0) {
    el.convList.innerHTML = '<p style="padding:16px;font-size:12px;color:var(--ink-500);">No conversations yet.</p>';
    return;
  }
  for (const c of state.conversations) {
    const item = document.createElement('div');
    item.className = 'conversation-item' + (c.id === state.activeId ? ' active' : '');
    item.dataset.id = c.id;

    const title = document.createElement('div');
    title.className = 'title';
    title.textContent = c.title || 'Untitled';

    const del = document.createElement('button');
    del.className = 'conv-delete';
    del.textContent = '×';
    del.title = 'Delete conversation';
    del.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm('Delete this conversation?')) return;
      await api.deleteConversation(c.id);
      if (state.activeId === c.id) {
        state.activeId = null;
        resetChatView();
      }
      await loadConversations();
    });

    item.appendChild(title);
    item.appendChild(del);
    item.addEventListener('click', () => openConversation(c.id));
    el.convList.appendChild(item);
  }
}

// function appendMessage(msg) {
//   if (el.emptyState) el.emptyState.style.display = 'none';

//   const wrap = document.createElement('div');
//   wrap.className = `message ${msg.role}`;

//   const avatar = document.createElement('div');
//   avatar.className = 'msg-avatar';
//   avatar.textContent = msg.role === 'user' ? initials(state.user.name) : 'AI';

//   const bubble = document.createElement('div');
//   bubble.className = 'msg-bubble';
//   bubble.textContent = msg.content;

//   // Citations panel (assistant messages only)
//   const citations = Array.isArray(msg.citations) ? msg.citations : [];
//   if (msg.role === 'assistant' && citations.length > 0) {
//     const panel = document.createElement('details');
//     panel.className = 'citations';

//     const summary = document.createElement('summary');
//     summary.textContent = `Sources (${citations.length})`;
//     panel.appendChild(summary);

//     citations.forEach((c, i) => {
//       const item = document.createElement('div');
//       item.className = 'citation';

//       const label = document.createElement('div');
//       label.className = 'citation-label';

//       const idx = document.createElement('span');
//       idx.className = 'citation-index';
//       idx.textContent = `[${i + 1}]`;

//       const source = document.createElement('span');
//       source.className = 'citation-source';
//       source.textContent = c.source || 'Unknown';
//       if (c.date) source.textContent += ` · ${c.date}`;

//       label.appendChild(idx);
//       label.appendChild(source);

//       const snippet = document.createElement('p');
//       snippet.className = 'citation-snippet';
//       snippet.textContent = c.text || '';

//       item.appendChild(label);
//       item.appendChild(snippet);

//       if (c.url) {
//         const link = document.createElement('a');
//         link.href = c.url;
//         link.target = '_blank';
//         link.rel = 'noopener noreferrer';
//         link.className = 'citation-link';
//         link.textContent = 'Open source ↗';
//         item.appendChild(link);
//       }

//       panel.appendChild(item);
//     });

//     bubble.appendChild(panel);
//   }

//   wrap.appendChild(avatar);
//   wrap.appendChild(bubble);
//   el.messages.appendChild(wrap);
//   el.messages.scrollTop = el.messages.scrollHeight;
// }

function appendMessage(msg) {
  if (el.emptyState) el.emptyState.style.display = 'none';

  const wrap = document.createElement('div');
  wrap.className = `message ${msg.role}`;

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.textContent = msg.role === 'user' ? initials(state.user.name) : 'AI';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';

  const citations = Array.isArray(msg.citations) ? msg.citations : [];

  // 1. Format the text and replace inline citations with numbered badges
  let formattedContent = msg.content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  if (msg.role === 'assistant' && citations.length > 0) {
    // Find patterns like 【source: X】 or [source: X]
    formattedContent = formattedContent.replace(
      /([\[【［]\s*source\s*:\s*([A-Za-z0-9_\-]+)\s*[\]】］])/gi,
      (match, full, sourceId) => {
        // Find which index this source corresponds to in the citations array
        const idx = citations.findIndex(c => c.source === sourceId);
        if (idx !== -1) {
          return `<span class="inline-cite" title="Source ${idx + 1}">[${idx + 1}]</span>`;
        }
        return match; // If not found, leave as is
      }
    );
  }

  // Parse simple newlines and bold text (**text**)
  formattedContent = formattedContent
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br />');

  bubble.innerHTML = formattedContent;

  // 2. Render the citations panel (if assistant message)
  if (msg.role === 'assistant' && citations.length > 0) {
    const panel = document.createElement('details');
    panel.className = 'citations';

    const summary = document.createElement('summary');
    summary.innerHTML = `<span class="cite-icon">📚</span> View Sources (${citations.length})`;
    panel.appendChild(summary);

    citations.forEach((c, i) => {
      const item = document.createElement('div');
      item.className = 'citation-card';
      if (c.cited) item.classList.add('is-cited');

      // Header: [1] Source Name
      const header = document.createElement('div');
      header.className = 'citation-header';
      header.innerHTML = `
        <span class="citation-index">[${i + 1}]</span>
        <span class="citation-source">${c.source || 'Unknown'}</span>
        ${c.cited ? '<span class="cited-badge">Cited</span>' : ''}
      `;

      // Meta tags: Tier, Page, Date, Score
      const meta = document.createElement('div');
      meta.className = 'citation-meta';
      
      const tags = [];
      if (c.tier) tags.push(`Tier ${c.tier}`);
      if (c.page) tags.push(`Page ${c.page}`);
      if (c.date) tags.push(c.date);
      if (c.similarity) tags.push(`Score: ${c.similarity.toFixed(2)}`);
      
      meta.innerHTML = tags.map(t => `<span class="meta-tag">${t}</span>`).join('');

      // Snippet
      const snippet = document.createElement('p');
      snippet.className = 'citation-snippet';
      snippet.textContent = c.text || '';

      item.appendChild(header);
      item.appendChild(meta);
      item.appendChild(snippet);
      panel.appendChild(item);
    });

    bubble.appendChild(panel);
  }

  wrap.appendChild(avatar);
  wrap.appendChild(bubble);
  el.messages.appendChild(wrap);
  el.messages.scrollTop = el.messages.scrollHeight;
}

function resetChatView() {
  el.messages.innerHTML = '';
  el.messages.appendChild(el.emptyState);
  el.emptyState.style.display = '';
  el.chatTitle.textContent = 'Select or start a conversation';
  el.chatSubtitle.textContent = 'Your research threads are saved here.';
  updateSendButton();
}

/* ---------- Data loading ---------- */
async function loadConversations() {
  state.conversations = await api.listConversations();
  renderConversations();
}

async function openConversation(id) {
  state.activeId = id;
  renderConversations();

  const convo = await api.getConversation(id);
  el.chatTitle.textContent = convo.title;
  el.chatSubtitle.textContent = `${convo.messages.length} message${convo.messages.length === 1 ? '' : 's'}`;

  el.messages.innerHTML = '';
  if (convo.messages.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.innerHTML = '<div class="empty-icon">💬</div><h3>New thread</h3><p>Send a message to begin.</p>';
    el.messages.appendChild(empty);
  } else {
    for (const m of convo.messages) appendMessage(m);
  }
  el.messages.scrollTop = el.messages.scrollHeight;
  updateSendButton();
}

async function createConversation() {
  const convo = await api.createConversation();
  await loadConversations();
  await openConversation(convo.id);
  el.input.focus();
}

/* ---------- Sending ---------- */
async function handleSend(e) {
  e.preventDefault();
  const content = el.input.value.trim();
  if (!content || !state.activeId) return;

  // Clear composer
  el.input.value = '';
  autoResize(el.input);
  updateSendButton();

  // Optimistic user bubble
  appendMessage({ role: 'user', content });

  // Typing indicator
  const typing = document.createElement('div');
  typing.className = 'message assistant';
  typing.innerHTML = `<div class="msg-avatar">AI</div><div class="msg-bubble">…thinking</div>`;
  el.messages.appendChild(typing);
  el.messages.scrollTop = el.messages.scrollHeight;

  try {
    const result = await api.sendMessage(state.activeId, content);
    typing.remove();
    appendMessage(result.assistantMessage);

    if (result.title && result.title !== el.chatTitle.textContent) {
      el.chatTitle.textContent = result.title;
      await loadConversations();
    }
  } catch (err) {
    typing.remove();
    appendMessage({ role: 'assistant', content: `⚠️ ${err.message}` });
  }
}

/* ---------- Init ---------- */
async function init() {
  try {
    state.user = await api.me();
  } catch {
    return;
  }

  el.userName.textContent = state.user.name;
  el.userEmail.textContent = state.user.email;
  el.userAvatar.textContent = initials(state.user.name);

  await loadConversations();
  updateSendButton();
}

/* ---------- Events ---------- */
el.composer.addEventListener('submit', handleSend);
el.input.addEventListener('input', () => { autoResize(el.input); updateSendButton(); });
el.input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    el.composer.requestSubmit();
  }
});
el.newChatBtn.addEventListener('click', createConversation);
el.logoutBtn.addEventListener('click', () => {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  window.location.href = '/index.html';
});

init();