import { send } from "../../shared/api";
import type { AnalyzeResult, Msg } from "../../shared/types";

export interface VibeCardProps {
  parent: HTMLElement;
  result: AnalyzeResult;
  onClose: () => void;
}

export function renderVibeCard(props: VibeCardProps): HTMLElement {
  const { parent, result, onClose } = props;
  const card = document.createElement("div");
  card.className = "vr-card";

  const score = document.createElement("div");
  score.className = "vr-score";
  score.textContent = `${result.match_score}%`;
  card.appendChild(score);

  const summary = document.createElement("div");
  summary.className = "vr-summary";
  summary.textContent = result.summary;
  card.appendChild(summary);

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
