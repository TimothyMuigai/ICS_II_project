require('dotenv').config();
const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const path = require('path');
const db = require('./db');

const app = express();
const PORT = process.env.PORT || 3000;
const JWT_SECRET = process.env.JWT_SECRET;

// server.js — after `const PORT = ...`
const RAG_URL = process.env.RAG_URL || 'http://127.0.0.1:8000';

if (!JWT_SECRET) {
  console.error('FATAL: JWT_SECRET is not set in .env');
  process.exit(1);
}

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

/* ---------------- Auth middleware ---------------- */
function auth(req, res, next) {
  const header = req.headers.authorization || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : null;
  if (!token) return res.status(401).json({ error: 'Missing token' });
  try {
    req.user = jwt.verify(token, JWT_SECRET);
    next();
  } catch {
    res.status(401).json({ error: 'Invalid or expired token' });
  }
}

function signToken(user) {
  return jwt.sign(
    { userId: user.id, email: user.email },
    JWT_SECRET,
    { expiresIn: '7d' }
  );
}

/* ---------------- Auth routes ---------------- */
app.post('/api/register', async (req, res) => {
  const { name, email, password } = req.body || {};
  if (!name || !email || !password) {
    return res.status(400).json({ error: 'Name, email and password are required' });
  }
  if (password.length < 8) {
    return res.status(400).json({ error: 'Password must be at least 8 characters' });
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: 'Invalid email format' });
  }

  const normalizedEmail = email.toLowerCase().trim();
  const existing = db.prepare('SELECT id FROM users WHERE email = ?').get(normalizedEmail);
  if (existing) return res.status(409).json({ error: 'Email already registered' });

  const hash = await bcrypt.hash(password, 12);
  const info = db.prepare(
    'INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)'
  ).run(name.trim(), normalizedEmail, hash);

  const user = { id: info.lastInsertRowid, name: name.trim(), email: normalizedEmail };
  res.status(201).json({ token: signToken(user), user });
});

app.post('/api/login', async (req, res) => {
  const { email, password } = req.body || {};
  if (!email || !password) {
    return res.status(400).json({ error: 'Email and password are required' });
  }

  const user = db.prepare('SELECT * FROM users WHERE email = ?')
    .get(email.toLowerCase().trim());
  if (!user) return res.status(401).json({ error: 'Invalid credentials' });

  const valid = await bcrypt.compare(password, user.password_hash);
  if (!valid) return res.status(401).json({ error: 'Invalid credentials' });

  res.json({
    token: signToken(user),
    user: { id: user.id, name: user.name, email: user.email },
  });
});

app.get('/api/me', auth, (req, res) => {
  const user = db.prepare(
    'SELECT id, name, email, created_at FROM users WHERE id = ?'
  ).get(req.user.userId);
  if (!user) return res.status(404).json({ error: 'User not found' });
  res.json(user);
});

/* ---------------- Conversation routes ---------------- */
app.get('/api/conversations', auth, (req, res) => {
  const convos = db.prepare(
    'SELECT id, title, created_at, updated_at FROM conversations WHERE user_id = ? ORDER BY updated_at DESC'
  ).all(req.user.userId);
  res.json(convos);
});

app.post('/api/conversations', auth, (req, res) => {
  const title = (req.body?.title || 'New chat').toString().slice(0, 200);
  const info = db.prepare(
    'INSERT INTO conversations (user_id, title) VALUES (?, ?)'
  ).run(req.user.userId, title);
  const convo = db.prepare('SELECT * FROM conversations WHERE id = ?')
    .get(info.lastInsertRowid);
  res.status(201).json(convo);
});

app.get('/api/conversations/:id', auth, (req, res) => {
  const convo = db.prepare(
    'SELECT * FROM conversations WHERE id = ? AND user_id = ?'
  ).get(req.params.id, req.user.userId);
  if (!convo) return res.status(404).json({ error: 'Conversation not found' });

  const messages = db.prepare(
    'SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC'
  ).all(convo.id);

  res.json({ ...convo, messages });
});

app.delete('/api/conversations/:id', auth, (req, res) => {
  const info = db.prepare(
    'DELETE FROM conversations WHERE id = ? AND user_id = ?'
  ).run(req.params.id, req.user.userId);
  if (info.changes === 0) return res.status(404).json({ error: 'Not found' });
  res.json({ ok: true });
});

/* ---------------- Chat endpoint (mock RAG) ---------------- */
/**
 * In production, replace `generateMockReply` with your RAG pipeline:
 *   1. Embed the user question
 *   2. Retrieve top-k chunks from your vector store (CMA/NSE/press corpus)
 *   3. Call the LLM with those chunks as context
 *   4. Return the answer + citations
 */
// function generateMockReply(text) {
//   const m = text.toLowerCase();
//   if (m.includes('safaricom') || m.includes('scom')) {
//     return "Safaricom (SCOM) is the largest NSE counter by market cap. To evaluate it, check three things: (1) the latest dividend declaration from CMA filings, (2) M-PESA's revenue contribution in the most recent annual report, and (3) any recent Communications Authority regulatory updates.\n\n[Demo response — the RAG pipeline will retrieve and cite these specific filings.]";
//   }
//   if (m.includes('dividend')) {
//     return "For NSE dividend research, the authoritative sources are the company's most recent annual report and CMA disclosures. Dividends are typically declared at the AGM and paid within 30–60 days. Verify the ex-dividend date and withholding tax (5% residents / 15% non-residents) before acting.\n\n[Demo response — RAG will cite the specific filing.]";
//   }
//   if (m.includes('cma') || m.includes('capital markets')) {
//     return "The Capital Markets Authority publishes quarterly and annual reports, licensing updates, and enforcement actions. These are essential for regulatory-risk analysis on NSE counters.\n\n[Demo response — RAG will retrieve the exact CMA document.]";
//   }
//   if (m.includes('risk')) {
//     return "Key risks for NSE retail investors: KES/USD volatility, election-cycle political risk, liquidity risk on small-cap counters, and concentration risk (a few large caps dominate the index).\n\n[Demo response — RAG will ground each risk in specific market data.]";
//   }
//   return "I'm your NSE research assistant. In production I'll ground every answer in CMA filings, NSE reports, and other verified Kenyan sources — with citations. This demo returns mock replies until the RAG pipeline is connected. Try asking about Safaricom, dividends, CMA filings, or market risks.";
// }

// server.js — replaces generateMockReply()

// app.post('/api/conversations/:id/chat', auth, (req, res) => {
//   const convo = db.prepare(
//     'SELECT * FROM conversations WHERE id = ? AND user_id = ?'
//   ).get(req.params.id, req.user.userId);
//   if (!convo) return res.status(404).json({ error: 'Conversation not found' });

//   const content = (req.body?.content || '').toString().trim();
//   if (!content) return res.status(400).json({ error: 'Message cannot be empty' });
//   if (content.length > 4000) return res.status(400).json({ error: 'Message too long' });

//   const insertMsg = db.prepare(
//     'INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)'
//   );
//   const userMsg = insertMsg.run(convo.id, 'user', content);

//   const reply = generateMockReply(content);
//   const assistantMsg = insertMsg.run(convo.id, 'assistant', reply);

//   // Auto-title on first user message
//   let newTitle = convo.title;
//   if (convo.title === 'New chat') {
//     newTitle = content.slice(0, 60) + (content.length > 60 ? '…' : '');
//     db.prepare('UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?')
//       .run(newTitle, convo.id);
//   } else {
//     db.prepare('UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?')
//       .run(convo.id);
//   }

//   res.json({
//     userMessage: db.prepare('SELECT * FROM messages WHERE id = ?').get(userMsg.lastInsertRowid),
//     assistantMessage: db.prepare('SELECT * FROM messages WHERE id = ?').get(assistantMsg.lastInsertRowid),
//     title: newTitle,
//   });
// });

app.get('/api/conversations/:id', auth, (req, res) => {
    const convo = db.prepare(
    'SELECT * FROM conversations WHERE id = ? AND user_id = ?'
    ).get(req.params.id, req.user.userId);
    if (!convo) return res.status(404).json({ error: 'Conversation not found' });

    const messages = db.prepare(
    'SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC'
    ).all(convo.id).map((m) => ({
    ...m,
    citations: m.citations ? JSON.parse(m.citations) : [],
    }));

    res.json({ ...convo, messages });
});

async function callRAG(question) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120_000); // 2 min

    try {
    const res = await fetch(`${RAG_URL}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, top_k: 5 }),
        signal: controller.signal,
    });

    if (!res.ok) {
        const detail = await res.text().catch(() => '');
        throw new Error(`RAG service error ${res.status}: ${detail.slice(0, 200)}`);
    }

    const data = await res.json();
    return {
        answer: data.answer,
        citations: Array.isArray(data.citations) ? data.citations : [],
        elapsedMs: data.elapsed_ms ?? null,
    };
    } catch (err) {
    if (err.name === 'AbortError') {
        throw new Error('RAG service timed out after 120s');
    }
    if (err.code === 'ECONNREFUSED') {
        throw new Error('RAG service unreachable — is FastAPI running on :8000?');
    }
    throw err;
    } finally {
    clearTimeout(timeout);
    }
}

app.post('/api/conversations/:id/chat', auth, async (req, res) => {
  const convo = db.prepare(
    'SELECT * FROM conversations WHERE id = ? AND user_id = ?'
  ).get(req.params.id, req.user.userId);
  if (!convo) return res.status(404).json({ error: 'Conversation not found' });

  const content = (req.body?.content || '').toString().trim();
  if (!content) return res.status(400).json({ error: 'Message cannot be empty' });
  if (content.length > 4000) return res.status(400).json({ error: 'Message too long' });

  // Persist user message first (so history is preserved even if RAG fails)
  const userMsg = db.prepare(
    'INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)'
  ).run(convo.id, 'user', content);

  // ── Call the RAG service ──
  let ragResult;
  try {
    ragResult = await callRAG(content);
  } catch (err) {
    console.error('[chat] RAG error:', err.message);
    // Save an error bubble so the user can see what happened
    const errMsg = db.prepare(
      'INSERT INTO messages (conversation_id, role, content, citations) VALUES (?, ?, ?, ?)'
    ).run(convo.id, 'assistant', `⚠️ ${err.message}`, JSON.stringify([]));

    return res.status(502).json({
      error: err.message,
      userMessage: db.prepare('SELECT * FROM messages WHERE id = ?').get(userMsg.lastInsertRowid),
      assistantMessage: {
        ...db.prepare('SELECT * FROM messages WHERE id = ?').get(errMsg.lastInsertRowid),
        citations: [],
      },
    });
  }

  // Persist assistant message with citations as JSON
  const assistantMsg = db.prepare(
    'INSERT INTO messages (conversation_id, role, content, citations) VALUES (?, ?, ?, ?)'
  ).run(
    convo.id,
    'assistant',
    ragResult.answer,
    JSON.stringify(ragResult.citations)
  );

  // Auto-title on first message
  let newTitle = convo.title;
  if (convo.title === 'New chat') {
    newTitle = content.slice(0, 60) + (content.length > 60 ? '…' : '');
    db.prepare('UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?')
      .run(newTitle, convo.id);
  } else {
    db.prepare('UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?')
      .run(convo.id);
  }

  res.json({
    userMessage: db.prepare('SELECT * FROM messages WHERE id = ?').get(userMsg.lastInsertRowid),
    assistantMessage: {
      ...db.prepare('SELECT * FROM messages WHERE id = ?').get(assistantMsg.lastInsertRowid),
      citations: ragResult.citations,
    },
    title: newTitle,
    elapsedMs: ragResult.elapsedMs,
  });
});

/* ---------------- Fallback ---------------- */
app.get('/', (_req, res) => res.sendFile(path.join(__dirname, 'public', 'index.html')));

// Optional: warn at startup if RAG service isn't reachable
fetch(`${RAG_URL}/health`)
  .then((r) => (r.ok ? console.log(`✅ RAG service reachable at ${RAG_URL}`) : Promise.reject(r.status)))
  .catch(() => console.warn(`⚠️  RAG service NOT reachable at ${RAG_URL} — chats will fail until it's up`));

app.listen(PORT, () => {
  console.log(`✅ NSE Assistant running at http://localhost:${PORT}`);
});