import { send } from "../shared/api";
import type { RadarResult } from "../shared/types";

async function main() {
  const root = document.getElementById("root")!;
  try {
    const data = await send<RadarResult>({ type: "GET_RADAR" });
    if (data.interaction_count > 0) {
      // Established user — show radar
      const mod = await import("./radar");
      await mod.renderRadar(root, data);
    } else if (data.has_personality) {
      // Zero interaction but already answered (or skipped) the quiz — show welcome
      const mod = await import("./welcome");
      mod.renderWelcome(root);
    } else {
      // Brand-new user — show personality quiz
      // Also clear the content script's flag so it will intercept highlights
      chrome.storage.local.remove("personality_completed");
      const mod = await import("./personality");
      await mod.renderPersonalityQuiz(root);
    }
  } catch (e: any) {
    root.innerHTML = `<div class="error">加载失败: ${e?.message ?? "未知"}</div>`;
  }
}

main();
