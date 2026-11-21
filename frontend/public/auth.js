// auth.js
// If already logged in, skip auth page
const existingToken = localStorage.getItem('token');
if (existingToken) {
  fetch('/api/me', { headers: { Authorization: `Bearer ${existingToken}` } })
    .then((r) => { if (r.ok) window.location.href = '/app.html'; })
    .catch(() => {});
}

// Tab switching
document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
    tab.classList.add('active');
    const target = tab.dataset.tab;
    document.getElementById('login-form').classList.toggle('hidden', target !== 'login');
    document.getElementById('register-form').classList.toggle('hidden', target !== 'register');
  });
});

function persistSession(body) {
  localStorage.setItem('token', body.token);
  localStorage.setItem('user', JSON.stringify(body.user));
  window.location.href = '/app.html';
}

async function submitForm(url, formEl, errEl, loadingText, idleText) {
  errEl.textContent = '';
  const data = Object.fromEntries(new FormData(formEl));
  const btn = formEl.querySelector('button[type=submit]');
  btn.disabled = true;
  btn.textContent = loadingText;

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || 'Request failed');
    persistSession(body);
  } catch (err) {
    errEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = idleText;
  }
}

document.getElementById('login-form').addEventListener('submit', (e) => {
  e.preventDefault();
  submitForm('/api/login', e.target, document.getElementById('login-error'),
    'Signing in…', 'Sign in');
});

document.getElementById('register-form').addEventListener('submit', (e) => {
  e.preventDefault();
  submitForm('/api/register', e.target, document.getElementById('register-error'),
    'Creating account…', 'Create account');
});