(function() {
if (window.__vibeRadarLoaded) return;
window.__vibeRadarLoaded = true;

const API = 'http://localhost:8000/api/v1';
const MIN_LEN = 2, MAX_LEN = 200;

// ═══════ Styles ═══════
const CSS = `
:host { all: initial; }
:host {
  --bg: linear-gradient(145deg, rgba(248,245,255,0.97), rgba(240,237,255,0.95));
  --border: rgba(108,92,231,0.15);
  --shadow: 0 8px 40px rgba(108,92,231,0.12), 0 2px 8px rgba(0,0,0,0.06);
  --text: #2d2545;
  --dim: rgba(108,92,231,0.6);
  --accent: #6c5ce7;
  --accent-bg: rgba(108,92,231,0.08);
  --accent-border: rgba(108,92,231,0.18);
  --green: #00b894; --green-bg: rgba(0,184,148,0.08); --green-border: rgba(0,184,148,0.2);
  --yellow: #e17055; --yellow-bg: rgba(225,112,85,0.08); --yellow-border: rgba(225,112,85,0.2);
  --red: #d63031; --red-bg: rgba(214,48,49,0.06); --red-border: rgba(214,48,49,0.15);
}
:host(.dark) {
  --bg: linear-gradient(145deg, rgba(18,12,38,0.97), rgba(25,18,48,0.95));
  --border: rgba(130,120,255,0.25);
  --shadow: 0 12px 48px rgba(0,0,0,0.5);
  --text: #f0eef8;
  --dim: rgba(200,195,230,0.65);
  --accent: #b8b0ff;
  --accent-bg: rgba(108,92,231,0.15);
  --accent-border: rgba(108,92,231,0.25);
  --green: #6cf5d6; --green-bg: rgba(85,239,196,0.15); --green-border: rgba(85,239,196,0.35);
  --yellow: #ffe8a0; --yellow-bg: rgba(253,203,110,0.15); --yellow-border: rgba(253,203,110,0.35);
  --red: #ff8a8a; --red-bg: rgba(255,118,117,0.13); --red-border: rgba(255,118,117,0.3);
}
.vr-root { font-family: -apple-system,"PingFang SC","Microsoft YaHei",sans-serif; color: var(--text); position: absolute; pointer-events: none; }
.vr-icon { width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg,#6c5ce7,#a29bfe,#fd79a8); background-size: 200% 200%; animation: vr-shift 3s ease infinite; box-shadow: 0 0 16px rgba(108,92,231,0.5); cursor: pointer; pointer-events: auto; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 15px; transition: transform 0.2s; }
.vr-icon:hover { transform: scale(1.15); }
@keyframes vr-shift { 0%,100% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } }
.vr-card { position: absolute; top: 40px; left: 0; width: 340px; background: var(--bg); backdrop-filter: blur(20px); border-radius: 16px; border: 1px solid var(--border); box-shadow: var(--shadow); padding: 20px; pointer-events: auto; font-size: 13px; line-height: 1.6; color: var(--text); overflow: hidden; }
.vr-card::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, rgba(108,92,231,0.5), rgba(253,121,168,0.4), transparent); }
.vr-score { font-size: 42px; font-weight: 800; background: linear-gradient(135deg,#a29bfe,#6c5ce7,#fd79a8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.vr-badge { display: inline-block; padding: 4px 14px; border-radius: 20px; font-size: 12px; font-weight: 700; letter-spacing: 2px; margin: 6px 0 8px; }
.vr-badge-g { background: var(--green-bg); color: var(--green); border: 1px solid var(--green-border); }
.vr-badge-y { background: var(--yellow-bg); color: var(--yellow); border: 1px solid var(--yellow-border); }
.vr-badge-r { background: var(--red-bg); color: var(--red); border: 1px solid var(--red-border); }
.vr-roast { font-size: 14px; font-weight: 500; color: var(--text); margin: 10px 0 12px; line-height: 1.7; }
.vr-actions { display: flex; gap: 10px; }
.vr-btn { flex: 1; padding: 10px; border: none; border-radius: 12px; cursor: pointer; font-size: 13px; font-weight: 600; transition: all 0.2s; }
.vr-btn:hover { transform: translateY(-2px); }
.vr-btn-g { background: var(--green-bg); color: var(--green); border: 1px solid var(--green-border); }
.vr-btn-r { background: var(--red-bg); color: var(--red); border: 1px solid var(--red-border); }
.vr-toolbar { display: flex; gap: 6px; margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--accent-border); }
.vr-tool { flex: 1; padding: 7px; font-size: 11px; color: var(--dim); background: var(--accent-bg); border: 1px solid var(--accent-border); border-radius: 8px; cursor: pointer; text-align: center; transition: all 0.2s; }
.vr-tool:hover { color: var(--accent); border-color: var(--accent); }
.vr-bar { width: 100%; height: 3px; background: var(--accent-bg); border-radius: 2px; margin: 0 0 10px; overflow: hidden; }
.vr-fill { height: 100%; width: 0%; background: linear-gradient(90deg,#6c5ce7,#a29bfe,#fd79a8); border-radius: 2px; transition: width 1s ease; }
.vr-steps { display: flex; justify-content: space-between; margin-bottom: 4px; }
.vr-step { font-size: 10px; color: var(--dim); opacity: 0.4; transition: all 0.4s; }
.vr-step.on { opacity: 1; font-weight: 600; color: var(--accent); }
.vr-error { color: var(--red); text-align: center; padding: 16px; }
.vr-hint { font-size: 11px; color: var(--dim); margin-top: 2px; }
`;

// ═══════ Shadow DOM Setup ═══════
let host, shadow, root, icon, card;

function setup() {
  host = document.createElement('div');
  host.id = 'vibe-radar-host';
  host.style.cssText = 'position:absolute;top:0;left:0;z-index:2147483647;';
  shadow = host.attachShadow({ mode: 'open' });
  const style = document.createElement('style');
  style.textContent = CSS;
  shadow.appendChild(style);
  root = document.createElement('div');
  root.className = 'vr-root';
  shadow.appendChild(root);
  document.body.appendChild(host);
  if (localStorage.getItem('vr_theme') === 'dark') host.classList.add('dark');
}

function clearUI() { root.innerHTML = ''; icon = null; card = null; }

function toggleTheme() {
  const isDark = host.classList.toggle('dark');
  localStorage.setItem('vr_theme', isDark ? 'dark' : 'light');
}

// ═══════ SSE Analyze ═══════
async function analyze(text) {
  // Check personality
  if (!localStorage.getItem('vr_personality_done')) {
    showQuiz(text);
    return;
  }

  // Check cache
  const cacheKey = 'vr_cache_' + text;
  const cached = localStorage.getItem(cacheKey);
  if (cached) { showResult(JSON.parse(cached), text); return; }

  // Show loading
  card = document.createElement('div');
  card.className = 'vr-card';
  card.innerHTML = '<div class="vr-bar"><div class="vr-fill" id="vr-fill"></div></div><div class="vr-steps"><span class="vr-step on">搜索</span><span class="vr-step">识别</span><span class="vr-step">分析</span></div>';
  icon.appendChild(card);

  const fill = card.querySelector('#vr-fill');
  const steps = card.querySelectorAll('.vr-step');
  const STEP = { searching: [15,0], identified: [55,1], judging: [75,2] };

  try {
    const r = await fetch(API + '/vibe/analyze-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, domain: 'movie', context: { page_title: document.title, page_url: location.href }, hesitation_ms: 1000 }),
    });
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '', evt = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split('\n'); buf = lines.pop() || '';
      for (const line of lines) {
        if (line.startsWith('event: ')) evt = line.slice(7).trim();
        else if (line.startsWith('data: ') && evt) {
          const d = JSON.parse(line.slice(6));
          if (evt === 'step' && STEP[d.step]) {
            fill.style.width = STEP[d.step][0] + '%';
            steps.forEach((s,i) => s.classList.toggle('on', i <= STEP[d.step][1]));
          } else if (evt === 'done') {
            localStorage.setItem(cacheKey, JSON.stringify(d));
            card.remove();
            showResult(d, text);
          } else if (evt === 'error') {
            card.innerHTML = '<div class="vr-error">' + (d.message || '分析失败') + '</div>';
            setTimeout(clearUI, 3000);
          }
          evt = '';
        }
      }
    }
  } catch (e) {
    card.innerHTML = '<div class="vr-error">后端未运行</div>';
    setTimeout(clearUI, 3000);
  }
}

// ═══════ Show Result ═══════
function showResult(data, text) {
  card = document.createElement('div');
  card.className = 'vr-card';
  const v = data.verdict || '看心情';
  const vc = v === '追' ? 'g' : v === '跳过' ? 'r' : 'y';

  let html = `<div class="vr-score">${data.match_score}%</div>`;
  html += `<div class="vr-badge vr-badge-${vc}">${v}</div>`;
  if (data.item_name) html += `<div class="vr-hint">${data.item_name}</div>`;
  html += '<div class="vr-roast" id="vr-roast"></div>';
  html += '<div class="vr-actions"><button class="vr-btn vr-btn-g" id="vr-star">👍 太准了吧</button><button class="vr-btn vr-btn-r" id="vr-bomb">🤔 差点意思</button></div>';
  html += '<div class="vr-toolbar"><button class="vr-tool" id="vr-retry">↻ 重新识别</button><button class="vr-tool" id="vr-theme">🌓</button></div>';
  card.innerHTML = html;
  icon.appendChild(card);

  // Typewriter
  const roastEl = card.querySelector('#vr-roast');
  const roast = data.roast || data.summary || '';
  let i = 0;
  const t = setInterval(() => { if (i < roast.length) roastEl.textContent += roast[i++]; else clearInterval(t); }, 20);

  // Actions
  card.querySelector('#vr-star').onclick = (e) => { e.stopPropagation(); sendAction('star', data); };
  card.querySelector('#vr-bomb').onclick = (e) => { e.stopPropagation(); sendAction('bomb', data); };
  card.querySelector('#vr-retry').onclick = (e) => {
    e.stopPropagation();
    localStorage.removeItem('vr_cache_' + text);
    card.remove();
    analyze(text);
  };
  card.querySelector('#vr-theme').onclick = (e) => { e.stopPropagation(); toggleTheme(); };
}

async function sendAction(action, data) {
  try {
    await fetch(API + '/vibe/action', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, matched_tag_ids: data.matched_tags.map(t => t.tag_id), text_hash: data.text_hash, read_ms: 3000, item_name: data.item_name, domain: 'movie', match_score: data.match_score, verdict: data.verdict }),
    });
    card.querySelectorAll('.vr-btn').forEach(b => { b.textContent = '✓ 收到'; b.disabled = true; });
    setTimeout(clearUI, 1500);
  } catch {}
}

// ═══════ Inline Quiz ═══════
function showQuiz(text) {
  const consts = ['白羊座','金牛座','双子座','巨蟹座','狮子座','处女座','天秤座','天蝎座','射手座','摩羯座','水瓶座','双鱼座'];
  card = document.createElement('div');
  card.className = 'vr-card';
  card.innerHTML = `
    <div style="font-size:15px;font-weight:700;color:var(--accent);margin-bottom:6px">先让 Vibe 认识你</div>
    <div class="vr-hint" style="margin-bottom:12px">填写后分析更准，也可跳过</div>
    <div class="vr-hint" style="font-weight:600;margin-bottom:4px">MBTI</div>
    <input type="text" id="vr-mbti" placeholder="INTP" maxlength="4" style="width:100%;padding:8px 12px;border:1px solid var(--accent-border);border-radius:8px;background:var(--accent-bg);color:var(--text);font-size:13px;box-sizing:border-box;margin-bottom:8px" />
    <div class="vr-hint" style="font-weight:600;margin-bottom:4px">星座</div>
    <select id="vr-const" style="width:100%;padding:8px 12px;border:1px solid var(--accent-border);border-radius:8px;background:var(--accent-bg);color:var(--text);font-size:13px;box-sizing:border-box;appearance:none">
      <option value="">—— 不填 ——</option>
      ${consts.map(c => '<option value="'+c+'">'+c+'</option>').join('')}
    </select>
    <div class="vr-actions" style="margin-top:12px">
      <button class="vr-btn vr-btn-r" id="vr-skip" style="border:1px solid var(--accent-border);color:var(--dim);background:var(--accent-bg)">跳过</button>
      <button class="vr-btn vr-btn-g" id="vr-submit" style="background:linear-gradient(135deg,#6c5ce7,#a29bfe);color:#fff;border:none">确认</button>
    </div>
    <div class="vr-hint" id="vr-qmsg" style="text-align:center;margin-top:8px;color:var(--accent)"></div>
  `;
  icon.appendChild(card);

  async function submit(mbti, constellation) {
    card.querySelector('#vr-qmsg').textContent = 'Vibe 正在理解你…';
    card.querySelector('#vr-submit').disabled = true;
    card.querySelector('#vr-skip').disabled = true;
    try {
      await fetch(API + '/personality/submit', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mbti, constellation }),
      });
      localStorage.setItem('vr_personality_done', '1');
      card.querySelector('#vr-qmsg').textContent = '✓ 开始分析…';
      setTimeout(() => { card.remove(); analyze(text); }, 600);
    } catch (e) {
      card.querySelector('#vr-qmsg').textContent = '提交失败';
      card.querySelector('#vr-submit').disabled = false;
      card.querySelector('#vr-skip').disabled = false;
    }
  }

  card.querySelector('#vr-skip').onclick = (e) => { e.stopPropagation(); submit(null, null); };
  card.querySelector('#vr-submit').onclick = (e) => {
    e.stopPropagation();
    const mbti = card.querySelector('#vr-mbti').value.trim().toUpperCase() || null;
    const constellation = card.querySelector('#vr-const').value || null;
    submit(mbti, constellation);
  };
}

// ═══════ Mouseup Handler ═══════
setup();
document.addEventListener('mouseup', (e) => {
  if (e.target.closest && e.target.closest('#vibe-radar-host')) return;
  const sel = window.getSelection();
  const text = (sel?.toString() || '').trim();
  if (text.length < MIN_LEN || text.length > MAX_LEN) { clearUI(); return; }

  const range = sel.getRangeAt(0);
  const rect = range.getBoundingClientRect();
  clearUI();

  icon = document.createElement('div');
  icon.style.cssText = `position:absolute;left:${rect.right+window.scrollX}px;top:${rect.top+window.scrollY}px;pointer-events:auto;`;
  const btn = document.createElement('div');
  btn.className = 'vr-icon';
  btn.textContent = '✦';
  btn.onclick = () => analyze(text);
  icon.appendChild(btn);
  root.appendChild(icon);
});

document.addEventListener('keydown', (e) => { if (e.key === 'Escape') clearUI(); });
document.addEventListener('mousedown', (e) => {
  if (icon && !e.target.closest('#vibe-radar-host')) clearUI();
});

console.log('✦ Vibe-Radar 已加载');
})();
