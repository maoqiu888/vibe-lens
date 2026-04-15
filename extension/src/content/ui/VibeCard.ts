import { send } from "../../shared/api";
import type { ActionResult, AnalyzeResult, Domain, Msg } from "../../shared/types";
import { playLevelUpAnimation } from "./LevelUpOverlay";
import { renderRecommendCard } from "./RecommendCard";
import { copyPosterToClipboard, downloadPoster, generatePoster } from "./SharePoster";

export interface VibeCardProps {
  parent: HTMLElement;
  result: AnalyzeResult;
  sourceDomain: Domain;
  text: string;
  onClose: () => void;
}

export function renderVibeCard(props: VibeCardProps): HTMLElement {
  const { parent, result, sourceDomain, text, onClose } = props;
  const card = document.createElement("div");
  card.className = "vr-card";
  const cardShownAt = performance.now();

  // Share button (top-right corner)
  const shareBtn = document.createElement("button");
  shareBtn.className = "vr-share-btn";
  shareBtn.textContent = "📤";
  shareBtn.title = "生成分享海报";
  let dialogOpen = false;
  shareBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    if (dialogOpen) return;
    dialogOpen = true;
    const dialog = buildShareDialog(card, result, sourceDomain, () => {
      dialog.remove();
      dialogOpen = false;
    });
    card.appendChild(dialog);
  });
  card.appendChild(shareBtn);

  if (result.ui_stage === "learning") {
    // L1-L3: hide the numeric percentage; show a level badge instead
    const badge = document.createElement("div");
    badge.className = "vr-learning-badge";
    badge.innerHTML = `
      <div class="vr-learning-emoji">${result.level_emoji}</div>
      <div class="vr-learning-title">Lv.${result.level} ${result.level_title}</div>
      <div class="vr-learning-sub">学习中 · 第 ${result.interaction_count} 次</div>
    `;
    card.appendChild(badge);
  } else {
    // L4+ show the percentage
    const score = document.createElement("div");
    score.className = "vr-score";
    score.textContent = `${result.match_score}%`;
    card.appendChild(score);

    if (result.ui_stage === "early") {
      // L4-L5: small level hint below the score
      const hint = document.createElement("div");
      hint.className = "vr-level-hint";
      hint.textContent = `${result.level_emoji} Lv.${result.level} ${result.level_title}`;
      card.appendChild(hint);
    }
    // "stable" (L6+) shows nothing extra
  }

  // Roast is the primary copy; if empty, fall back to showing summary as primary
  const hasRoast = typeof result.roast === "string" && result.roast.trim() !== "";

  if (hasRoast) {
    const roast = document.createElement("div");
    roast.className = "vr-roast";
    roast.textContent = result.roast;
    card.appendChild(roast);

    if (result.summary && result.summary.trim() !== "") {
      const summary = document.createElement("div");
      summary.className = "vr-summary";
      summary.textContent = result.summary;
      card.appendChild(summary);
    }
  } else {
    // Fall back: promote summary to primary styling
    const roastFallback = document.createElement("div");
    roastFallback.className = "vr-roast";
    roastFallback.textContent = result.summary || "";
    card.appendChild(roastFallback);
  }

  const actions = document.createElement("div");
  actions.className = "vr-actions";

  const star = document.createElement("button");
  star.className = "vr-btn star";
  star.textContent = "❤️ 我喜欢";
  star.addEventListener("click", async () => {
    const readMs = Math.max(0, Math.round(performance.now() - cardShownAt));
    try {
      const actionResult = await sendAction("star", result, readMs);
      star.textContent = "✓ 已确权";
      handlePostActionLevelUp(card, actionResult, onClose);
    } catch {
      star.textContent = "提交失败";
      setTimeout(onClose, 1500);
    }
  });

  const bomb = document.createElement("button");
  bomb.className = "vr-btn bomb";
  bomb.textContent = "👎 我不喜欢";
  bomb.addEventListener("click", async () => {
    const readMs = Math.max(0, Math.round(performance.now() - cardShownAt));
    try {
      const actionResult = await sendAction("bomb", result, readMs);
      bomb.textContent = "✓ 已标记";
      handlePostActionLevelUp(card, actionResult, onClose);
    } catch {
      bomb.textContent = "提交失败";
      setTimeout(onClose, 1500);
    }
  });

  actions.appendChild(star);
  actions.appendChild(bomb);
  card.appendChild(actions);

  // V1.3: first-time onboarding hint under the action row.
  chrome.storage.local.get("has_seen_onboarding").then((stored) => {
    if (!stored.has_seen_onboarding) {
      const hint = document.createElement("div");
      hint.className = "vr-onboarding-hint";
      hint.textContent = "点这两个按钮，让 Vibe 越来越懂你 · 点得越多越准";
      card.appendChild(hint);
      chrome.storage.local.set({ has_seen_onboarding: true });
    }
  });

  // Recommend link (lazy trigger at the very bottom)
  const recommendLink = document.createElement("a");
  recommendLink.className = "vr-recommend-link";
  recommendLink.textContent = "> 寻找同频代餐";
  recommendLink.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    recommendLink.style.display = "none";
    renderRecommendCard({
      parent: card,
      text,
      sourceDomain,
      matchedTagIds: result.matched_tags.map((t) => t.tag_id),
    });
  });
  card.appendChild(recommendLink);

  parent.appendChild(card);
  return card;
}

async function sendAction(
  action: "star" | "bomb",
  result: AnalyzeResult,
  readMs: number,
): Promise<ActionResult> {
  const msg: Msg = {
    type: "ACTION",
    payload: {
      action,
      matchedTagIds: result.matched_tags.map((t) => t.tag_id),
      textHash: result.text_hash,
      readMs,
    },
  };
  return await send<ActionResult>(msg);
}

function handlePostActionLevelUp(
  card: HTMLElement,
  actionResult: ActionResult,
  onClose: () => void,
): void {
  if (!actionResult.level_up) {
    setTimeout(onClose, 1500);
    return;
  }
  // Play level-up overlay on top of the existing vibe card, then close
  playLevelUpAnimation(card, actionResult, () => {
    setTimeout(onClose, 400);
  });
}

function buildShareDialog(
  card: HTMLElement,
  result: AnalyzeResult,
  sourceDomain: Domain,
  onClose: () => void,
): HTMLElement {
  const dialog = document.createElement("div");
  dialog.className = "vr-share-dialog";

  const copyBtn = document.createElement("button");
  copyBtn.textContent = "📋 复制到剪贴板";
  copyBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    const canvas = generatePoster(result, sourceDomain);
    try {
      await copyPosterToClipboard(canvas);
      showToast(card, "已复制到剪贴板");
    } catch (err) {
      showToast(card, "剪贴板失败，已自动下载");
      downloadPoster(canvas);
    }
    onClose();
  });

  const downloadBtn = document.createElement("button");
  downloadBtn.textContent = "💾 下载 PNG";
  downloadBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const canvas = generatePoster(result, sourceDomain);
    downloadPoster(canvas);
    showToast(card, "已下载");
    onClose();
  });

  const cancelBtn = document.createElement("button");
  cancelBtn.textContent = "取消";
  cancelBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    onClose();
  });

  dialog.appendChild(copyBtn);
  dialog.appendChild(downloadBtn);
  dialog.appendChild(cancelBtn);
  return dialog;
}

function showToast(parent: HTMLElement, text: string): void {
  const toast = document.createElement("div");
  toast.className = "vr-toast";
  toast.textContent = text;
  parent.appendChild(toast);
  setTimeout(() => toast.remove(), 2000);
}
