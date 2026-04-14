import { send } from "../shared/api";
import type { CategoryCard, ColdStartCardsResult, ColdStartSubmitResult } from "../shared/types";

type Selections = Record<string, number>;

export async function renderColdStart(root: HTMLElement, onDone: () => void) {
  root.innerHTML = `
    <h2>Vibe-Radar 冷启动</h2>
    <div class="subtitle">每行挑一张最像你的，让我先认识你</div>
    <div id="cards"></div>
    <button class="submit" id="submit">请先完成 6 个选择</button>
  `;

  const cardsRoot = root.querySelector("#cards") as HTMLElement;
  const submitBtn = root.querySelector("#submit") as HTMLButtonElement;
  const selections: Selections = {};

  try {
    const data = await send<ColdStartCardsResult>({ type: "COLD_START_GET_CARDS" });
    for (const card of data.cards) {
      cardsRoot.appendChild(renderCategoryCard(card, selections, () =>
        updateSubmit(submitBtn, selections)
      ));
    }
  } catch (e: any) {
    cardsRoot.innerHTML = `<div class="error">加载失败: ${e?.message ?? "未知"}</div>`;
    return;
  }

  submitBtn.addEventListener("click", async () => {
    if (Object.keys(selections).length !== 6) return;
    const ids = Object.values(selections);
    try {
      await send<ColdStartSubmitResult>({
        type: "COLD_START_SUBMIT",
        payload: { selectedTagIds: ids },
      });
      await chrome.storage.local.set({ profile_initialized: true });
      onDone();
    } catch (e: any) {
      submitBtn.textContent = `提交失败: ${e?.message ?? "未知"}`;
    }
  });
}

function renderCategoryCard(card: CategoryCard, selections: Selections, onChange: () => void): HTMLElement {
  const wrap = document.createElement("div");
  wrap.className = "category";
  wrap.innerHTML = `<div class="category-label">${card.category_label}</div>`;
  const opts = document.createElement("div");
  opts.className = "options";
  for (const o of card.options) {
    const el = document.createElement("div");
    el.className = "option";
    el.innerHTML = `
      <div class="option-name">${o.name}</div>
      <div class="option-tagline">${o.tagline}</div>
      <div class="option-examples">${o.examples.join(" · ")}</div>
    `;
    el.addEventListener("click", () => {
      opts.querySelectorAll(".option").forEach((n) => n.classList.remove("selected"));
      el.classList.add("selected");
      selections[card.category] = o.tag_id;
      onChange();
    });
    opts.appendChild(el);
  }
  wrap.appendChild(opts);
  return wrap;
}

function updateSubmit(btn: HTMLButtonElement, selections: Selections) {
  const done = Object.keys(selections).length === 6;
  btn.classList.toggle("enabled", done);
  btn.textContent = done ? "开始鉴定" : `还差 ${6 - Object.keys(selections).length} 个`;
}
