import type { ActionResult, AnalyzeResult } from "../../shared/types";

type LevelUpSource = AnalyzeResult | ActionResult;

const PREV_LEVEL_EMOJI: Record<number, string> = {
  0: "👤",
  1: "🌱",
  2: "🌿",
  3: "🌳",
  4: "🔍",
  5: "🎯",
  6: "🧠",
  7: "💞",
  8: "🔮",
  9: "👻",
  10: "💎",
};

function prevLevelEmoji(newLevel: number): string {
  const prev = Math.max(0, newLevel - 1);
  const capped = Math.min(prev, 10);
  return PREV_LEVEL_EMOJI[capped] ?? "👤";
}

export function playLevelUpAnimation(
  container: HTMLElement,
  result: LevelUpSource,
  onDone: () => void,
): HTMLElement {
  const overlay = document.createElement("div");
  overlay.className = "vr-levelup-overlay";
  overlay.innerHTML = `
    <div class="vr-levelup-old">${prevLevelEmoji(result.level)}</div>
    <div class="vr-levelup-arrows">↓ ↓ ↓</div>
    <div class="vr-levelup-new">${result.level_emoji}</div>
    <div class="vr-levelup-title">Lv.${result.level} ${result.level_title}</div>
    <div class="vr-levelup-sub">🎉 你已经喂了 ${result.interaction_count} 个信号</div>
    <button class="vr-levelup-skip" title="跳过">×</button>
  `;
  container.appendChild(overlay);

  const skipBtn = overlay.querySelector(".vr-levelup-skip") as HTMLButtonElement;
  let finished = false;

  const finish = () => {
    if (finished) return;
    finished = true;
    overlay.style.opacity = "0";
    setTimeout(() => {
      overlay.remove();
      onDone();
    }, 300);
  };

  skipBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    finish();
  });

  setTimeout(finish, 1500);

  return overlay;
}
