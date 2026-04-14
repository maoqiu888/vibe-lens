import { send } from "../../shared/api";
import type { Domain, Msg, RecommendItem, RecommendResult } from "../../shared/types";

const DOMAIN_EMOJI: Record<Domain, string> = {
  book: "📚",
  movie: "🎬",
  game: "🎮",
  music: "🎵",
};

export interface RecommendCardProps {
  parent: HTMLElement;
  text: string;
  sourceDomain: Domain;
  matchedTagIds: number[];
}

export function renderRecommendCard(props: RecommendCardProps): HTMLElement {
  const card = document.createElement("div");
  card.className = "vr-card vr-recommend-card";
  const body = document.createElement("div");
  body.className = "vr-recommend-body";
  card.appendChild(body);

  const rerollBtn = document.createElement("button");
  rerollBtn.className = "vr-btn vr-reroll";
  rerollBtn.textContent = "换一批 ↻";
  rerollBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    await loadAndRender(body, rerollBtn, props);
  });
  card.appendChild(rerollBtn);

  props.parent.appendChild(card);
  void loadAndRender(body, rerollBtn, props);

  return card;
}

async function loadAndRender(
  body: HTMLElement,
  btn: HTMLButtonElement,
  props: RecommendCardProps,
): Promise<void> {
  btn.disabled = true;
  body.innerHTML = "";
  const loading = document.createElement("div");
  loading.className = "vr-recommend-loading";
  loading.textContent = "代餐官思考中…";
  body.appendChild(loading);

  const msg: Msg = {
    type: "RECOMMEND",
    payload: {
      text: props.text,
      sourceDomain: props.sourceDomain,
      matchedTagIds: props.matchedTagIds,
    },
  };

  try {
    const result = await send<RecommendResult>(msg);
    body.innerHTML = "";
    for (const item of result.items) {
      body.appendChild(renderItem(item));
    }
  } catch (e: any) {
    body.innerHTML = "";
    const err = document.createElement("div");
    err.className = "vr-recommend-error";
    err.textContent = e?.message?.includes("NO_CROSS_DOMAIN")
      ? "这次没灵感，换一个物品试试"
      : "代餐官去冲咖啡了，稍后再试";
    body.appendChild(err);
  } finally {
    btn.disabled = false;
  }
}

function renderItem(item: RecommendItem): HTMLElement {
  const row = document.createElement("div");
  row.className = "vr-recommend-item";
  const head = document.createElement("div");
  head.className = "vr-recommend-name";
  head.textContent = `${DOMAIN_EMOJI[item.domain]} ${item.name}`;
  const reason = document.createElement("div");
  reason.className = "vr-recommend-reason";
  reason.textContent = item.reason;
  row.appendChild(head);
  row.appendChild(reason);
  return row;
}
