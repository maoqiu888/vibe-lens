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

function showPersonalityPrompt(parent: HTMLElement) {
  const card = document.createElement("div");
  card.className = "vr-card vr-personality-prompt";
  card.innerHTML = `
    <div class="vr-prompt-title">先让 Vibe 认识你 ✋</div>
    <div class="vr-prompt-sub">填写 MBTI 或星座，分析结果更准</div>
    <div class="vr-prompt-actions">
      <button class="vr-btn vr-btn-go">去设置</button>
      <button class="vr-btn vr-btn-skip">跳过</button>
    </div>
  `;
  const goBtn = card.querySelector(".vr-btn-go") as HTMLButtonElement;
  const skipBtn = card.querySelector(".vr-btn-skip") as HTMLButtonElement;

  goBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    chrome.runtime.sendMessage({ type: "OPEN_PERSONALITY" });
    card.remove();
    clearUi();
  });

  skipBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    chrome.storage.local.set({ personality_completed: true });
    try {
      await send({ type: "PERSONALITY_SUBMIT", payload: { mbti: null, constellation: null } } as any);
    } catch { /* best effort */ }
    card.remove();
  });

  parent.appendChild(card);
}

async function onIconClick(text: string, domain: Domain) {
  if (!currentIcon) return;

  const stored = await chrome.storage.local.get("personality_completed");
  if (!stored.personality_completed) {
    showPersonalityPrompt(currentIcon);
    return;
  }

  // Show stepped loading animation
  const loading = document.createElement("div");
  loading.className = "vr-card vr-loading";
  loading.innerHTML = `
    <div class="vr-ping">
      <div class="vr-ping-ring"></div>
      <div class="vr-ping-ring"></div>
      <div class="vr-ping-ring"></div>
      <div class="vr-ping-core"></div>
    </div>
    <div class="vr-loading-text"><span class="vr-step-text">正在联网搜索</span><span class="vr-loading-dots"></span></div>
    <div class="vr-step-bar"><div class="vr-step-fill"></div></div>
    <div class="vr-step-labels">
      <span class="vr-step-label active">搜索</span>
      <span class="vr-step-label">识别</span>
      <span class="vr-step-label">分析</span>
    </div>
    <div class="vr-shimmer-bar"></div>
  `;

  const steps = [
    { text: "正在联网搜索", pct: 20, delay: 0 },
    { text: "正在识别作品", pct: 50, delay: 1500 },
    { text: "正在匹配分析", pct: 80, delay: 3500 },
  ];
  const stepText = loading.querySelector(".vr-step-text") as HTMLElement;
  const stepFill = loading.querySelector(".vr-step-fill") as HTMLElement;
  const stepLabels = loading.querySelectorAll(".vr-step-label");
  const stepTimers: number[] = [];

  for (let i = 0; i < steps.length; i++) {
    const timer = window.setTimeout(() => {
      stepText.textContent = steps[i].text;
      stepFill.style.width = `${steps[i].pct}%`;
      stepLabels.forEach((l, j) => l.classList.toggle("active", j <= i));
    }, steps[i].delay);
    stepTimers.push(timer);
  }
  currentIcon.appendChild(loading);

  const hesitationMs = iconShownAt !== null
    ? Math.max(0, Math.round(performance.now() - iconShownAt))
    : null;

  const msg: Msg = {
    type: "ANALYZE",
    payload: {
      text,
      domain,
      pageTitle: document.title,
      pageUrl: location.href,
      hesitationMs,
    },
  };

  try {
    const result = await send<AnalyzeResult>(msg);
    stepTimers.forEach(clearTimeout);
    stepFill.style.width = "100%";
    loading.remove();

    if (result.level_up) {
      // Play celebration first, then render the real card
      const tempCard = document.createElement("div");
      tempCard.className = "vr-card";
      currentIcon.appendChild(tempCard);
      playLevelUpAnimation(tempCard, result, () => {
        tempCard.remove();
        if (!currentIcon) return;
        currentCard = renderVibeCard({
          parent: currentIcon,
          result,
          sourceDomain: domain,
          text,
          onClose: clearUi,
        });
      });
    } else {
      currentCard = renderVibeCard({
        parent: currentIcon,
        result,
        sourceDomain: domain,
        text,
        onClose: clearUi,
      });
    }
  } catch (e: any) {
    stepTimers.forEach(clearTimeout);
    loading.className = "vr-card vr-error";
    loading.textContent = e?.message?.startsWith("BACKEND_DOWN")
      ? "后端未运行，请先启动 FastAPI"
      : `鉴定失败: ${e?.message ?? "未知错误"}`;
    setTimeout(clearUi, 3000);
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
