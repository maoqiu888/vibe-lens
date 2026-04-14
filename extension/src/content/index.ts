import { send } from "../shared/api";
import { MAX_TEXT_LEN, MIN_TEXT_LEN } from "../shared/constants";
import type { AnalyzeResult, Domain, Msg } from "../shared/types";
import { detectDomain } from "./domain";
import { renderFloatingIcon } from "./ui/FloatingIcon";
import { renderVibeCard } from "./ui/VibeCard";
import INLINE_CSS from "./ui/styles.css?inline";

let shadowRoot: ShadowRoot | null = null;
let currentIcon: HTMLElement | null = null;
let currentCard: HTMLElement | null = null;

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
}

async function onIconClick(text: string, domain: Domain) {
  if (!currentIcon) return;
  // Show loading state inside the icon's wrap
  const loading = document.createElement("div");
  loading.className = "vr-card vr-loading";
  loading.innerHTML = `
    <div class="vr-ping">
      <div class="vr-ping-ring"></div>
      <div class="vr-ping-ring"></div>
      <div class="vr-ping-ring"></div>
      <div class="vr-ping-core"></div>
    </div>
    <div class="vr-loading-text">正在读取你的审美指纹<span class="vr-loading-dots"></span></div>
    <div class="vr-shimmer-bar"></div>
  `;
  currentIcon.appendChild(loading);

  const msg: Msg = {
    type: "ANALYZE",
    payload: {
      text,
      domain,
      pageTitle: document.title,
      pageUrl: location.href,
    },
  };

  try {
    const result = await send<AnalyzeResult>(msg);
    loading.remove();
    currentCard = renderVibeCard({
      parent: currentIcon,
      result,
      sourceDomain: domain,
      text,
      onClose: clearUi,
    });
  } catch (e: any) {
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
