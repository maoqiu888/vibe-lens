import { send } from "../../shared/api";
import type { AnalyzeResult, Domain, Msg } from "../../shared/types";
import { copyPosterToClipboard, downloadPoster, generatePoster } from "./SharePoster";

export interface VibeCardProps {
  parent: HTMLElement;
  result: AnalyzeResult;
  sourceDomain: Domain;
  onClose: () => void;
}

export function renderVibeCard(props: VibeCardProps): HTMLElement {
  const { parent, result, sourceDomain, onClose } = props;
  const card = document.createElement("div");
  card.className = "vr-card";

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

  const score = document.createElement("div");
  score.className = "vr-score";
  score.textContent = `${result.match_score}%`;
  card.appendChild(score);

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

  const tagsWrap = document.createElement("div");
  tagsWrap.className = "vr-tags";
  for (const t of result.matched_tags) {
    const pill = document.createElement("span");
    pill.className = "vr-tag";
    pill.textContent = t.name;
    tagsWrap.appendChild(pill);
  }
  card.appendChild(tagsWrap);

  const actions = document.createElement("div");
  actions.className = "vr-actions";

  const star = document.createElement("button");
  star.className = "vr-btn star";
  star.textContent = "💎 懂我";
  star.addEventListener("click", async () => {
    await sendAction("star", result);
    star.textContent = "✓ 已确权";
    setTimeout(onClose, 1500);
  });

  const bomb = document.createElement("button");
  bomb.className = "vr-btn bomb";
  bomb.textContent = "💣 踩雷";
  bomb.addEventListener("click", async () => {
    await sendAction("bomb", result);
    bomb.textContent = "✓ 已标记";
    setTimeout(onClose, 1500);
  });

  actions.appendChild(star);
  actions.appendChild(bomb);
  card.appendChild(actions);

  parent.appendChild(card);
  return card;
}

async function sendAction(action: "star" | "bomb", result: AnalyzeResult) {
  const msg: Msg = {
    type: "ACTION",
    payload: {
      action,
      matchedTagIds: result.matched_tags.map((t) => t.tag_id),
      textHash: result.text_hash,
    },
  };
  try {
    await send(msg);
  } catch (e) {
    console.warn("[vibe-radar] action failed", e);
  }
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
