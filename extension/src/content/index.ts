import { send } from "../shared/api";
import { MAX_TEXT_LEN, MIN_TEXT_LEN } from "../shared/constants";
import type { AnalyzeResult, Domain, Msg } from "../shared/types";
import { detectDomain } from "./domain";
import { renderFloatingIcon } from "./ui/FloatingIcon";
import { playLevelUpAnimation } from "./ui/LevelUpOverlay";
import { renderVibeCard } from "./ui/VibeCard";
import INLINE_CSS from "./ui/styles.css?inline";

let shadowRoot: ShadowRoot | null = null;
let currentIcon: HTMLElement | null = null;
let currentCard: HTMLElement | null = null;
let iconShownAt: number | null = null;

function ensureShadow(): ShadowRoot {
  if (shadowRoot) return shadowRoot;
  const host = document.createElement("div");
  host.id = "vibe-radar-host";
  host.style.cssText = "position:absolute;top:0;left:0;z-index:2147483647;";
  const root = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = INLINE_CSS;
  root.appendChild(style);
  document.body.appendChild(host);
  shadowRoot = root;
  return root;
}

function clearUi() {
  currentIcon?.remove();
  currentIcon = null;
  currentCard?.remove();
  currentCard = null;
  iconShownAt = null;
}

const CONSTELLATIONS = [
  "白羊座", "金牛座", "双子座", "巨蟹座", "狮子座", "处女座",
  "天秤座", "天蝎座", "射手座", "摩羯座", "水瓶座", "双鱼座",
];

function showPersonalityPrompt(parent: HTMLElement, onDone: () => void) {
  const card = document.createElement("div");
  card.className = "vr-card vr-personality-prompt";
  card.innerHTML = `
    <div class="vr-prompt-title">先让 Vibe 认识你</div>
    <div class="vr-prompt-sub">填写后分析更准，也可以跳过</div>
    <label class="vr-field-label">MBTI <span style="color:#999;font-size:10px">（可选）</span></label>
    <input type="text" class="vr-quiz-input" placeholder="INTP" maxlength="4" />
    <label class="vr-field-label">星座 <span style="color:#999;font-size:10px">（可选）</span></label>
    <select class="vr-quiz-select">
      <option value="">—— 不填 ——</option>
      ${CONSTELLATIONS.map((c) => `<option value="${c}">${c}</option>`).join("")}
    </select>
    <div class="vr-prompt-actions">
      <button class="vr-btn vr-btn-skip">跳过</button>
      <button class="vr-btn vr-btn-go">确认</button>
    </div>
    <div class="vr-quiz-msg"></div>
  `;
  const mbtiInput = card.querySelector(".vr-quiz-input") as HTMLInputElement;
  const constellationSelect = card.querySelector(".vr-quiz-select") as HTMLSelectElement;
  const submitBtn = card.querySelector(".vr-btn-go") as HTMLButtonElement;
  const skipBtn = card.querySelector(".vr-btn-skip") as HTMLButtonElement;
  const msg = card.querySelector(".vr-quiz-msg") as HTMLElement;

  async function submit(mbti: string | null, constellation: string | null) {
    submitBtn.disabled = true;
    skipBtn.disabled = true;
    msg.textContent = "Vibe 正在理解你…";
    try {
      await send({ type: "PERSONALITY_SUBMIT", payload: { mbti, constellation } } as any);
      chrome.storage.local.set({ personality_completed: true });
      msg.textContent = "✓ 开始分析…";
      setTimeout(() => { card.remove(); onDone(); }, 600);
    } catch (e: any) {
      msg.textContent = `提交失败: ${e?.message ?? "未知"}`;
      submitBtn.disabled = false;
      skipBtn.disabled = false;
    }
  }

  skipBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    submit(null, null);
  });
  submitBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const mbti = mbtiInput.value.trim().toUpperCase() || null;
    const constellation = constellationSelect.value || null;
    submit(mbti, constellation);
  });

  parent.appendChild(card);
}

async function onIconClick(text: string, domain: Domain, excludeItems?: string[]) {
  if (!currentIcon) return;

  if (!excludeItems) {
    const stored = await chrome.storage.local.get("personality_completed");
    if (!stored.personality_completed) {
      showPersonalityPrompt(currentIcon, () => onIconClick(text, domain));
      return;
    }
  }

  // Check frontend cache (skip on retry)
  if (!excludeItems) {
    const cacheKey = `vr_cache_${text}_${domain}`;
    const cached = await chrome.storage.local.get(cacheKey);
    if (cached[cacheKey]) {
      const result = cached[cacheKey] as AnalyzeResult;
      const retryHandler = (newExcludes: string[]) => {
        chrome.storage.local.remove(cacheKey);
        currentCard?.remove();
        currentCard = null;
        onIconClick(text, domain, newExcludes);
      };
      currentCard = renderVibeCard({
        parent: currentIcon,
        result,
        sourceDomain: domain,
        text,
        onClose: clearUi,
        onRetry: retryHandler,
      });
      return;
    }
  }

  // SSE streaming card
  const card = document.createElement("div");
  card.className = "vr-card vr-stream-card";
  card.innerHTML = `
    <div class="vr-stream-step">
      <div class="vr-step-bar"><div class="vr-step-fill"></div></div>
      <div class="vr-step-labels">
        <span class="vr-step-label active">搜索</span>
        <span class="vr-step-label">识别</span>
        <span class="vr-step-label">分析</span>
      </div>
    </div>
    <div class="vr-stream-score" style="display:none"></div>
    <div class="vr-stream-verdict" style="display:none"></div>
    <div class="vr-stream-roast" style="display:none"></div>
    <div class="vr-stream-actions" style="display:none"></div>
  `;
  currentIcon.appendChild(card);
  currentCard = card;

  const stepFill = card.querySelector(".vr-step-fill") as HTMLElement;
  const stepLabels = card.querySelectorAll(".vr-step-label");
  const scoreEl = card.querySelector(".vr-stream-score") as HTMLElement;
  const verdictEl = card.querySelector(".vr-stream-verdict") as HTMLElement;
  const roastEl = card.querySelector(".vr-stream-roast") as HTMLElement;

  const STEP_MAP: Record<string, { pct: number; labels: number }> = {
    searching: { pct: 15, labels: 0 },
    identified: { pct: 55, labels: 1 },
    judging: { pct: 75, labels: 2 },
  };

  const hesitationMs = iconShownAt !== null
    ? Math.max(0, Math.round(performance.now() - iconShownAt))
    : null;

  const port = chrome.runtime.connect({ name: "analyze-stream" });
  let finalResult: AnalyzeResult | null = null;

  port.onMessage.addListener((msg: { event: string; data: any }) => {
    if (msg.event === "step") {
      const s = STEP_MAP[msg.data.step];
      if (s) {
        stepFill.style.width = `${s.pct}%`;
        stepLabels.forEach((l, j) => l.classList.toggle("active", j <= s.labels));
      }
    } else if (msg.event === "identified") {
      // Show score immediately (base_score, will be updated by done)
      scoreEl.style.display = "";
      scoreEl.innerHTML = `<span class="vr-score">${msg.data.base_score}%</span>`;
      scoreEl.querySelector(".vr-score")!.className = "vr-score";
    } else if (msg.event === "done") {
      finalResult = msg.data as AnalyzeResult;
      stepFill.style.width = "100%";

      // Hide progress bar
      const stepSection = card.querySelector(".vr-stream-step") as HTMLElement;
      stepSection.style.display = "none";

      // Update score to final
      scoreEl.innerHTML = `<span class="vr-score">${finalResult.match_score}%</span>`;

      // Show verdict badge
      const v = finalResult.verdict || "看心情";
      const colorClass = v === "追" ? "vr-verdict-green" : v === "跳过" ? "vr-verdict-red" : "vr-verdict-yellow";
      verdictEl.style.display = "";
      verdictEl.innerHTML = `<div class="vr-verdict-badge ${colorClass}">${v}</div>`;

      // Typewriter roast
      const roastText = finalResult.roast || finalResult.summary || "";
      roastEl.style.display = "";
      roastEl.className = "vr-roast vr-stream-roast";
      roastEl.textContent = "";
      let i = 0;
      const typeTimer = setInterval(() => {
        if (i < roastText.length) {
          roastEl.textContent += roastText[i];
          i++;
        } else {
          clearInterval(typeTimer);
          showStreamActions(card, finalResult!, text, domain, excludeItems);
        }
      }, 25);

      // Cache result
      const cacheKey = `vr_cache_${text}_${domain}`;
      chrome.storage.local.set({ [cacheKey]: finalResult });
    } else if (msg.event === "error") {
      card.className = "vr-card vr-error";
      card.textContent = msg.data.code === "BACKEND_DOWN"
        ? "后端未运行，请先启动 FastAPI"
        : `鉴定失败: ${msg.data.message ?? "未知错误"}`;
      setTimeout(clearUi, 3000);
    }
  });

  port.postMessage({
    payload: {
      text, domain,
      pageTitle: document.title,
      pageUrl: location.href,
      hesitationMs,
      excludeItems: excludeItems || undefined,
    },
  });
}

function showStreamActions(
  card: HTMLElement,
  result: AnalyzeResult,
  text: string,
  domain: Domain,
  excludeItems?: string[],
) {
  const cardShownAt = performance.now();
  const actions = document.createElement("div");
  actions.className = "vr-actions";

  const star = document.createElement("button");
  star.className = "vr-btn star";
  star.textContent = "👍 太准了吧";
  star.addEventListener("click", async () => {
    const readMs = Math.max(0, Math.round(performance.now() - cardShownAt));
    try {
      await send({ type: "ACTION", payload: {
        action: "star" as const, matchedTagIds: result.matched_tags.map(t => t.tag_id),
        textHash: result.text_hash, readMs, itemName: result.item_name,
        domain, matchScore: result.match_score, verdict: result.verdict,
      }} as any);
      star.textContent = "✓ 收到反馈";
      setTimeout(clearUi, 1500);
    } catch { star.textContent = "提交失败"; setTimeout(clearUi, 1500); }
  });

  const bomb = document.createElement("button");
  bomb.className = "vr-btn bomb";
  bomb.textContent = "🤔 差点意思";
  bomb.addEventListener("click", async () => {
    const readMs = Math.max(0, Math.round(performance.now() - cardShownAt));
    try {
      await send({ type: "ACTION", payload: {
        action: "bomb" as const, matchedTagIds: result.matched_tags.map(t => t.tag_id),
        textHash: result.text_hash, readMs, itemName: result.item_name,
        domain, matchScore: result.match_score, verdict: result.verdict,
      }} as any);
      bomb.textContent = "✓ 收到反馈";
      setTimeout(clearUi, 1500);
    } catch { bomb.textContent = "提交失败"; setTimeout(clearUi, 1500); }
  });

  actions.appendChild(star);
  actions.appendChild(bomb);
  card.appendChild(actions);

  // Recommend link
  const recommendLink = document.createElement("a");
  recommendLink.className = "vr-recommend-link";
  recommendLink.textContent = "> 寻找同频代餐";
  recommendLink.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    recommendLink.style.display = "none";
    renderRecommendCard({
      parent: card, text, sourceDomain: domain,
      matchedTagIds: result.matched_tags.map(t => t.tag_id),
    });
  });
  card.appendChild(recommendLink);

  // Retry link
  if (result.item_name) {
    const retryLink = document.createElement("a");
    retryLink.className = "vr-retry-link";
    retryLink.textContent = "✕ 不是这个，重新识别";
    retryLink.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const cacheKey = `vr_cache_${text}_${domain}`;
      chrome.storage.local.remove(cacheKey);
      const allExcludes = [...(excludeItems || []), result.item_name];
      currentCard?.remove();
      currentCard = null;
      onIconClick(text, domain, allExcludes);
    });
    card.appendChild(retryLink);
  }
}

document.addEventListener("mouseup", (e) => {
  if ((e.target as Element | null)?.closest("#vibe-radar-host")) return;
  const sel = window.getSelection();
  const text = sel?.toString().trim() ?? "";
  if (text.length < MIN_TEXT_LEN || text.length > MAX_TEXT_LEN) {
    clearUi();
    return;
  }

  const domain = detectDomain(location.href);
  if (!domain) return;

  const range = sel!.getRangeAt(0);
  const rect = range.getBoundingClientRect();

  clearUi();
  const root = ensureShadow();
  currentIcon = renderFloatingIcon(root, {
    x: rect.right + window.scrollX,
    y: rect.top + window.scrollY,
    onClick: () => onIconClick(text, domain),
  });
  iconShownAt = performance.now();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") clearUi();
});

document.addEventListener("mousedown", (e) => {
  // Click outside the shadow host → hide
  if (currentIcon && !(e.target as Element).closest("#vibe-radar-host")) {
    clearUi();
  }
});
